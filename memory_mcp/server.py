"""MCP server wiring for memory-mcp.

This module depends on the official ``mcp`` Python SDK. It is intentionally kept
free of any storage/search logic: everything substantive lives in
:mod:`memory_mcp.store`, which is standard-library only and independently
testable. The tests never import this module, so a missing ``mcp`` package
cannot break the store test suite.
"""

from __future__ import annotations

from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from memory_mcp.store import MemoryStore

# A single process-wide store instance. The path is resolved from the
# MEMORY_MCP_PATH environment variable (or the default) at import time.
_store = MemoryStore()

server: Server = Server("memory-mcp")


TOOLS: list[Tool] = [
    Tool(
        name="memory_write",
        description=(
            "Store or update a memory entry under a key. Overwrites content if "
            "the key already exists (created_at is preserved)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Unique identifier."},
                "content": {"type": "string", "description": "Text to remember."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels for filtering.",
                },
            },
            "required": ["key", "content"],
        },
    ),
    Tool(
        name="memory_read",
        description="Read a memory entry by its key. Returns the entry or a not-found message.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to read."},
            },
            "required": ["key"],
        },
    ),
    Tool(
        name="memory_search",
        description=(
            "Keyword search across stored entries (content, tags and key). "
            "Returns ranked matches with a short snippet."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms."},
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10).",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="memory_list",
        description="List all stored keys, optionally filtered by a tag.",
        inputSchema={
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "Optional tag to filter by.",
                },
            },
        },
    ),
    Tool(
        name="memory_delete",
        description="Delete a memory entry by key. Reports whether anything was removed.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to delete."},
            },
            "required": ["key"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


def _text(payload: str) -> list[TextContent]:
    return [TextContent(type="text", text=payload)]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    arguments = arguments or {}

    if name == "memory_write":
        entry = _store.write(
            key=arguments["key"],
            content=arguments["content"],
            tags=arguments.get("tags"),
        )
        tags = ", ".join(entry.tags) if entry.tags else "(none)"
        return _text(
            f"Stored '{entry.key}' (updated_at={entry.updated_at}). Tags: {tags}"
        )

    if name == "memory_read":
        entry = _store.read(arguments["key"])
        if entry is None:
            return _text(f"No entry found for key '{arguments['key']}'.")
        tags = ", ".join(entry.tags) if entry.tags else "(none)"
        return _text(
            f"key: {entry.key}\n"
            f"tags: {tags}\n"
            f"created_at: {entry.created_at}\n"
            f"updated_at: {entry.updated_at}\n"
            f"---\n{entry.content}"
        )

    if name == "memory_search":
        results = _store.search(
            arguments["query"], limit=int(arguments.get("limit", 10))
        )
        if not results:
            return _text(f"No matches for '{arguments['query']}'.")
        lines = [f"{len(results)} match(es) for '{arguments['query']}':"]
        for r in results:
            lines.append(f"- [{r.score}] {r.entry.key}: {r.snippet}")
        return _text("\n".join(lines))

    if name == "memory_list":
        entries = _store.list(tag=arguments.get("tag"))
        if not entries:
            suffix = f" with tag '{arguments['tag']}'" if arguments.get("tag") else ""
            return _text(f"No entries{suffix}.")
        lines = [f"{len(entries)} ent"
                 + ("ry" if len(entries) == 1 else "ries") + ":"]
        for e in entries:
            tags = f" [{', '.join(e.tags)}]" if e.tags else ""
            lines.append(f"- {e.key}{tags}")
        return _text("\n".join(lines))

    if name == "memory_delete":
        removed = _store.delete(arguments["key"])
        if removed:
            return _text(f"Deleted '{arguments['key']}'.")
        return _text(f"No entry found for key '{arguments['key']}'.")

    raise ValueError(f"Unknown tool: {name}")


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    import anyio

    anyio.run(_run)


if __name__ == "__main__":
    main()
