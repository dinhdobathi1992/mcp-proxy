# mcp-proxy

Thin FastMCP-based proxy that exposes multiple downstream MCP servers as one front MCP server.

Core features:

- package layout
- config loader with full validation
- `cwd` support for stdio backends
- stderr-only logging
- CLI entrypoint
- FastMCP proxy startup wiring
- client compatibility docs and config examples

Python 3.10+ is the intended runtime baseline.

## Goals

- One MCP server for the host to configure
- Many downstream MCP servers behind it
- `stdio` first for Claude Code, Codex, Cursor, and OpenCode
- Optional `http` front transport for remote deployments

## Quickstart Shape

Example downstream config:

```json
{
  "mcpServers": {
    "echo": {
      "command": "python3",
      "args": ["tests/fixtures/backend_stdio.py"]
    },
    "math": {
      "url": "http://127.0.0.1:9001/mcp",
      "transport": "http"
    }
  }
}
```

Validate config only:

```bash
mcp-proxy --config servers.example.json --check
```

Run as a local stdio server:

```bash
mcp-proxy --config servers.example.json
```

Run as an HTTP server:

```bash
mcp-proxy --config servers.example.json --transport http --host 127.0.0.1 --port 8000
```

## Compatibility Notes

- Logs are sent to stderr so MCP stdout stays clean.
- `stdio` is the primary target for local host integration.
- Example host configs live under `examples/`.
- Additional host notes live in `docs/client-compatibility.md`.
