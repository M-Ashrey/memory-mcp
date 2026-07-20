"""Pure storage and search logic for memory-mcp.

This module is intentionally dependency-free (standard library only) so that it
can be imported and unit-tested without the ``mcp`` SDK installed. It provides a
small JSON-file-backed key/value store with tags, timestamps, atomic writes and
a simple keyword search.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_STORE_PATH = Path.home() / ".memory-mcp" / "store.json"
_ENV_VAR = "MEMORY_MCP_PATH"


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def resolve_store_path(explicit: Optional[os.PathLike | str] = None) -> Path:
    """Resolve the store path from an explicit value, the env var, or the default.

    Precedence: ``explicit`` argument, then ``MEMORY_MCP_PATH``, then
    ``~/.memory-mcp/store.json``.
    """
    if explicit is not None:
        return Path(explicit).expanduser()
    env = os.environ.get(_ENV_VAR)
    if env:
        return Path(env).expanduser()
    return DEFAULT_STORE_PATH


@dataclass
class Entry:
    """A single memory entry."""

    key: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "content": self.content,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        return cls(
            key=data["key"],
            content=data.get("content", ""),
            tags=list(data.get("tags", [])),
            created_at=data.get("created_at", _utcnow()),
            updated_at=data.get("updated_at", _utcnow()),
        )


@dataclass
class SearchResult:
    """A ranked search hit with a short contextual snippet."""

    entry: Entry
    score: int
    snippet: str


def _normalize_tags(tags: Optional[Iterable[str]]) -> list[str]:
    """Lowercase, strip, de-duplicate (order preserved), and drop empties."""
    if not tags:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        norm = str(tag).strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def _make_snippet(content: str, terms: list[str], width: int = 120) -> str:
    """Build a short snippet, centered on the first matching term if any."""
    flat = " ".join(content.split())
    if not flat:
        return ""
    lowered = flat.lower()
    pos = -1
    for term in terms:
        found = lowered.find(term)
        if found != -1 and (pos == -1 or found < pos):
            pos = found
    if pos == -1 or len(flat) <= width:
        snippet = flat[:width]
        return snippet + ("..." if len(flat) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(flat), start + width)
    snippet = flat[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(flat) else ""
    return f"{prefix}{snippet}{suffix}"


class MemoryStore:
    """A JSON-file-backed memory store with atomic writes.

    The store keeps all entries in a single JSON file. Reads load the file on
    demand; writes rewrite the whole file atomically (temp file + ``os.replace``)
    so a crash mid-write cannot corrupt the store. A process-level lock guards
    against concurrent access from multiple threads in the same process.
    """

    def __init__(self, path: Optional[os.PathLike | str] = None) -> None:
        self.path = resolve_store_path(path)
        self._lock = threading.RLock()

    # -- persistence -------------------------------------------------------

    def _load(self) -> dict[str, Entry]:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        if not raw.strip():
            return {}
        data = json.loads(raw)
        entries: dict[str, Entry] = {}
        for item in data.get("entries", []):
            entry = Entry.from_dict(item)
            entries[entry.key] = entry
        return entries

    def _save(self, entries: dict[str, Entry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "entries": [entries[k].to_dict() for k in sorted(entries)],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        # Atomic write: write to a temp file in the same directory, then replace.
        fd, tmp_name = tempfile.mkstemp(
            prefix=".store-", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            # Best-effort cleanup of the temp file on failure.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # -- public API --------------------------------------------------------

    def write(
        self,
        key: str,
        content: str,
        tags: Optional[Iterable[str]] = None,
    ) -> Entry:
        """Create or update an entry, returning the stored :class:`Entry`.

        On update the ``created_at`` timestamp is preserved and ``updated_at``
        is refreshed.
        """
        if not key or not str(key).strip():
            raise ValueError("key must be a non-empty string")
        key = str(key)
        with self._lock:
            entries = self._load()
            now = _utcnow()
            existing = entries.get(key)
            if existing is None:
                entry = Entry(
                    key=key,
                    content=content,
                    tags=_normalize_tags(tags),
                    created_at=now,
                    updated_at=now,
                )
            else:
                entry = Entry(
                    key=key,
                    content=content,
                    tags=_normalize_tags(tags)
                    if tags is not None
                    else existing.tags,
                    created_at=existing.created_at,
                    updated_at=now,
                )
            entries[key] = entry
            self._save(entries)
            return entry

    def read(self, key: str) -> Optional[Entry]:
        """Return the entry for ``key`` or ``None`` if it does not exist."""
        with self._lock:
            return self._load().get(str(key))

    def delete(self, key: str) -> bool:
        """Delete an entry. Returns ``True`` if something was removed."""
        with self._lock:
            entries = self._load()
            if str(key) not in entries:
                return False
            del entries[str(key)]
            self._save(entries)
            return True

    def list(self, tag: Optional[str] = None) -> list[Entry]:
        """List entries, optionally filtered by ``tag``, sorted by key."""
        with self._lock:
            entries = self._load()
        result = list(entries.values())
        if tag:
            norm = str(tag).strip().lower()
            result = [e for e in result if norm in e.tags]
        result.sort(key=lambda e: e.key)
        return result

    def all_tags(self) -> list[str]:
        """Return the sorted set of tags used across all entries."""
        with self._lock:
            entries = self._load()
        tags: set[str] = set()
        for entry in entries.values():
            tags.update(entry.tags)
        return sorted(tags)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Rank entries by keyword hits across content, tags and key.

        The query is split into lowercased terms. For each entry the score is
        the total number of term occurrences in ``content`` plus weighted hits
        in ``tags`` (x3) and ``key`` (x2). Results are sorted by score
        descending, then by ``updated_at`` descending, and the top ``limit`` are
        returned with a short snippet.
        """
        terms = [t for t in query.lower().split() if t]
        if not terms:
            return []
        with self._lock:
            entries = self._load()

        results: list[SearchResult] = []
        for entry in entries.values():
            content_l = entry.content.lower()
            key_l = entry.key.lower()
            tags_l = " ".join(entry.tags)
            score = 0
            for term in terms:
                score += content_l.count(term)
                score += key_l.count(term) * 2
                score += tags_l.count(term) * 3
            if score > 0:
                results.append(
                    SearchResult(
                        entry=entry,
                        score=score,
                        snippet=_make_snippet(entry.content, terms),
                    )
                )
        results.sort(key=lambda r: (r.score, r.entry.updated_at), reverse=True)
        return results[:limit]
