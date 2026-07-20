"""Programmatic use of the memory-mcp store (no MCP transport required).

Run with:

    python examples/basic_usage.py

This writes to a throwaway store under the system temp directory so it will
not touch your real ~/.memory-mcp/store.json.
"""

import tempfile
from pathlib import Path

from memory_mcp import MemoryStore


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="memory-mcp-demo-")) / "store.json"
    store = MemoryStore(tmp)

    # Write a few entries with tags.
    store.write(
        "project/goals",
        "Ship the memory-mcp server and write a clear README.",
        tags=["project", "todo"],
    )
    store.write(
        "user/preferences",
        "Prefers concise answers and Python for backend work.",
        tags=["profile"],
    )
    store.write(
        "project/stack",
        "Python 3.10+, standard library only for storage, mcp SDK for transport.",
        tags=["project", "reference"],
    )

    # Read one back.
    entry = store.read("user/preferences")
    print("read user/preferences ->", entry.content if entry else "(missing)")

    # List everything, then filter by tag.
    print("\nall keys:", [e.key for e in store.list()])
    print("tagged 'project':", [e.key for e in store.list(tag="project")])
    print("known tags:", store.all_tags())

    # Keyword search, ranked with snippets.
    print("\nsearch 'python backend':")
    for hit in store.search("python backend"):
        print(f"  [{hit.score}] {hit.entry.key}: {hit.snippet}")

    # Update (created_at preserved) and delete.
    updated = store.write("project/goals", "Ship memory-mcp. Done!")
    print("\nupdated project/goals at", updated.updated_at)
    print("deleted project/stack:", store.delete("project/stack"))
    print("final keys:", [e.key for e in store.list()])


if __name__ == "__main__":
    main()
