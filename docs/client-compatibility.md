# Client Compatibility

This document captures the launch contract the proxy should satisfy for the primary target hosts:

- Claude Code
- Codex
- Cursor
- OpenCode

## Shared Contract

- Prefer `stdio` for local use.
- Use the venv binary: `.venv/bin/mcp-proxy`.
- Do not require shell wrappers.
- Do not emit logs to stdout.
- Accept all runtime configuration through command args and env vars.

The examples below use absolute paths to the venv binary. Adjust for your installation location.

## Claude Code

Project-scoped example:

```json
{
  "mcpServers": {
    "proxy": {
      "type": "stdio",
      "command": "/absolute/path/to/mcp-proxy/.venv/bin/mcp-proxy",
      "args": ["--config", "/absolute/path/to/servers.json"],
      "env": {}
    }
  }
}
```

## Codex

CLI registration example:

```bash
codex mcp add proxy -- /absolute/path/to/mcp-proxy/.venv/bin/mcp-proxy --config /absolute/path/to/servers.json
```

Config example:

```toml
[mcp_servers.proxy]
command = "/absolute/path/to/mcp-proxy/.venv/bin/mcp-proxy"
args = ["--config", "/absolute/path/to/servers.json"]
```

## Cursor

Project-scoped example:

```json
{
  "mcpServers": {
    "proxy": {
      "type": "stdio",
      "command": "/absolute/path/to/mcp-proxy/.venv/bin/mcp-proxy",
      "args": ["--config", "/absolute/path/to/servers.json"],
      "env": {}
    }
  }
}
```

Cursor also supports variable interpolation in several MCP config fields. A later delivery pass should prefer `${workspaceFolder}` or `${env:NAME}` where that improves checked-in project portability.

## OpenCode

Local server example:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "proxy": {
      "type": "local",
      "command": ["/absolute/path/to/mcp-proxy/.venv/bin/mcp-proxy", "--config", "/absolute/path/to/servers.json"],
      "enabled": true
    }
  }
}
```

## Testing the Connection

After configuring your client, verify the proxy works:

```bash
# Validate config
uv run mcp-proxy --config servers.json --check

# Test HTTP mode
uv run mcp-proxy --config servers.json --transport http --port 8001
# Then in another terminal:
curl -s http://127.0.0.1:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```
