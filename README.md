# memory-mcp

Persistent memory for AI agents over the [Model Context Protocol](https://modelcontextprotocol.io) (MCP). Filesystem-backed, dependency-light, with keyword search — so an agent can remember things across sessions without a database, embeddings, or API keys.

## Why

Most agents forget everything between runs. `memory-mcp` gives any MCP-compatible client (Claude Desktop, Claude Code, and others) five simple tools to write, read, search, list, and delete memories that persist on disk as plain JSON. The storage layer is standard-library only and independently tested, so it's easy to audit and hard to break.

## Tools

| Tool | What it does |
|------|--------------|
| `memory_write` | Store or update an entry under a key (with optional tags). |
| `memory_read` | Read an entry back by its key. |
| `memory_search` | Keyword search across content, tags, and keys — returns ranked snippets. |
| `memory_list` | List all keys, optionally filtered by tag. |
| `memory_delete` | Remove an entry by key. |

## Install

```bash
pip install git+https://github.com/M-Ashrey/memory-mcp
```

Requires Python 3.10+.

## Use with Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "memory-mcp"
    }
  }
}
```

By default, memories are stored under a local file resolved from the `MEMORY_MCP_PATH` environment variable. Set it to control where data lives:

```json
{
  "mcpServers": {
    "memory": {
      "command": "memory-mcp",
      "env": { "MEMORY_MCP_PATH": "/path/to/memory.json" }
    }
  }
}
```

## Develop

```bash
git clone https://github.com/M-Ashrey/memory-mcp
cd memory-mcp
pip install -e ".[dev]"
pytest
```

The store logic (`memory_mcp/store.py`) has no third-party dependencies and its tests never import the MCP server, so the test suite runs even without the `mcp` SDK installed.

## Related

Part of a small set of AI-agent tooling — see also the [Claude MCP starter kit](https://github.com/M-Ashrey/claude-mcp-starter-kit).

## License

MIT
