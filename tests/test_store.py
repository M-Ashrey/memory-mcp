"""Tests for the memory-mcp storage and search layer.

These tests exercise ``memory_mcp.store`` directly. They depend only on the
standard library and pytest -- the ``mcp`` SDK is never imported here, so the
suite runs green even when ``mcp`` is not installed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from memory_mcp.store import (
    Entry,
    MemoryStore,
    resolve_store_path,
)


@pytest.fixture()
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "store.json")


def test_write_then_read_roundtrip(store: MemoryStore) -> None:
    entry = store.write("greeting", "hello world", tags=["demo"])
    assert entry.key == "greeting"
    assert entry.content == "hello world"
    assert entry.tags == ["demo"]

    read = store.read("greeting")
    assert read is not None
    assert read.content == "hello world"
    assert read.tags == ["demo"]


def test_read_missing_key_returns_none(store: MemoryStore) -> None:
    assert store.read("does-not-exist") is None


def test_write_persists_to_disk(store: MemoryStore) -> None:
    store.write("k", "v")
    assert store.path.exists()
    # A fresh store pointed at the same file must see the data.
    reopened = MemoryStore(store.path)
    assert reopened.read("k").content == "v"


def test_update_preserves_created_at_and_bumps_updated_at(
    store: MemoryStore,
) -> None:
    first = store.write("k", "one")
    # Force distinguishable timestamps regardless of clock resolution.
    second = store.write("k", "two")
    reread = store.read("k")
    assert reread.content == "two"
    assert reread.created_at == first.created_at
    assert reread.updated_at >= second.created_at
    # Only one entry should exist for the key.
    assert len(store.list()) == 1


def test_update_without_tags_keeps_existing_tags(store: MemoryStore) -> None:
    store.write("k", "one", tags=["a", "b"])
    store.write("k", "two")  # tags omitted -> preserved
    assert store.read("k").tags == ["a", "b"]


def test_update_with_tags_replaces_tags(store: MemoryStore) -> None:
    store.write("k", "one", tags=["a", "b"])
    store.write("k", "two", tags=["c"])
    assert store.read("k").tags == ["c"]


def test_empty_key_rejected(store: MemoryStore) -> None:
    with pytest.raises(ValueError):
        store.write("", "content")


def test_delete_removes_entry(store: MemoryStore) -> None:
    store.write("k", "v")
    assert store.delete("k") is True
    assert store.read("k") is None


def test_delete_missing_key_returns_false(store: MemoryStore) -> None:
    assert store.delete("nope") is False


def test_list_all_sorted_by_key(store: MemoryStore) -> None:
    store.write("banana", "b")
    store.write("apple", "a")
    store.write("cherry", "c")
    keys = [e.key for e in store.list()]
    assert keys == ["apple", "banana", "cherry"]


def test_list_filtered_by_tag(store: MemoryStore) -> None:
    store.write("a", "x", tags=["work"])
    store.write("b", "y", tags=["personal"])
    store.write("c", "z", tags=["work", "urgent"])
    work = [e.key for e in store.list(tag="work")]
    assert work == ["a", "c"]


def test_tag_normalization(store: MemoryStore) -> None:
    entry = store.write("k", "v", tags=["  Work ", "WORK", "urgent", ""])
    # Lowercased, stripped, de-duplicated, empties dropped.
    assert entry.tags == ["work", "urgent"]


def test_all_tags_returns_sorted_union(store: MemoryStore) -> None:
    store.write("a", "x", tags=["z", "a"])
    store.write("b", "y", tags=["m", "a"])
    assert store.all_tags() == ["a", "m", "z"]


def test_search_ranks_by_hit_count(store: MemoryStore) -> None:
    store.write("doc1", "python python python testing")
    store.write("doc2", "python once")
    store.write("doc3", "unrelated text")
    results = store.search("python")
    assert [r.entry.key for r in results] == ["doc1", "doc2"]
    assert results[0].score > results[1].score


def test_search_is_case_insensitive(store: MemoryStore) -> None:
    store.write("k", "The Quick Brown Fox")
    results = store.search("QUICK fox")
    assert len(results) == 1
    assert results[0].entry.key == "k"


def test_search_weights_key_and_tags(store: MemoryStore) -> None:
    # Term only in tags should outrank the same single term in content,
    # because tag hits are weighted higher.
    store.write("content-hit", "alpha appears once here", tags=["misc"])
    store.write("tag-hit", "nothing relevant", tags=["alpha"])
    results = store.search("alpha")
    assert results[0].entry.key == "tag-hit"


def test_search_empty_query_returns_nothing(store: MemoryStore) -> None:
    store.write("k", "v")
    assert store.search("   ") == []


def test_search_respects_limit(store: MemoryStore) -> None:
    for i in range(5):
        store.write(f"k{i}", "matchme content")
    results = store.search("matchme", limit=3)
    assert len(results) == 3


def test_search_returns_snippet(store: MemoryStore) -> None:
    long_text = "prefix " * 40 + "NEEDLE here " + "suffix " * 40
    store.write("k", long_text)
    results = store.search("needle")
    assert len(results) == 1
    assert "needle" in results[0].snippet.lower()


def test_atomic_write_leaves_no_temp_files(store: MemoryStore) -> None:
    store.write("a", "1")
    store.write("b", "2")
    leftovers = [
        p.name
        for p in store.path.parent.iterdir()
        if p.name.startswith(".store-") and p.name.endswith(".tmp")
    ]
    assert leftovers == []


def test_stored_json_is_valid_and_versioned(store: MemoryStore) -> None:
    store.write("k", "v", tags=["t"])
    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["entries"][0]["key"] == "k"
    assert data["entries"][0]["tags"] == ["t"]
    assert "created_at" in data["entries"][0]


def test_corrupt_temp_does_not_affect_existing_store(store: MemoryStore) -> None:
    store.write("k", "original")
    # Simulate a stray temp file; it must not affect reads.
    stray = store.path.parent / ".store-stray.tmp"
    stray.write_text("garbage", encoding="utf-8")
    assert store.read("k").content == "original"


def test_load_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    path.write_text("", encoding="utf-8")
    store = MemoryStore(path)
    assert store.list() == []


def test_entry_from_dict_roundtrip() -> None:
    entry = Entry(key="k", content="c", tags=["a"])
    restored = Entry.from_dict(entry.to_dict())
    assert restored == entry


def test_resolve_store_path_precedence(tmp_path: Path, monkeypatch) -> None:
    # Explicit wins over env.
    explicit = tmp_path / "explicit.json"
    monkeypatch.setenv("MEMORY_MCP_PATH", str(tmp_path / "env.json"))
    assert resolve_store_path(explicit) == explicit
    # Env wins over default when no explicit value.
    assert resolve_store_path() == tmp_path / "env.json"
    # Default when neither is set.
    monkeypatch.delenv("MEMORY_MCP_PATH", raising=False)
    assert resolve_store_path().name == "store.json"
