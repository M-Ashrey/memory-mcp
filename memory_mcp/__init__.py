"""memory-mcp: filesystem-backed persistent memory for AI agents over MCP."""

from memory_mcp.store import (
    Entry,
    MemoryStore,
    SearchResult,
    resolve_store_path,
)

__all__ = [
    "Entry",
    "MemoryStore",
    "SearchResult",
    "resolve_store_path",
]

__version__ = "0.1.0"
