# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability in `memory-mcp`, please report it privately rather than opening a public issue.

- **Preferred:** open the repo's [Security tab -> Report a vulnerability](https://github.com/M-Ashrey/memory-mcp/security/advisories/new) (GitHub private advisory).
- **Alternative:** email m.ashrey122@gmail.com with subject `SECURITY: memory-mcp`.

Please include a description of the issue, steps to reproduce (a minimal example is ideal), and the potential impact. A suggested fix is welcome but not required.

This is a solo-maintained open-source project — there's no formal SLA, but security reports are treated as priority and acknowledged as soon as I see them, typically within a few days.

## Supported Versions

Only the latest release and the `main` branch are supported. There are no LTS branches at this stage.

## Scope

`memory-mcp` stores whatever content a client writes to it as plain JSON on local disk (path controlled by `MEMORY_MCP_PATH`). It does not encrypt memory contents at rest and is designed for single-user, local/trusted use — do not point it at a shared or multi-tenant filesystem path. Treat the store file like any other local config file that may contain notes an agent chose to remember.
