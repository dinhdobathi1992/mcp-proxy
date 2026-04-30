# Client Compatibility

This document captures the launch contract the proxy should satisfy for the primary target hosts:

- Claude Code
- Codex
- Cursor
- OpenCode

## Shared Contract

- Prefer `stdio` for local use.
- Use one stable executable: `mcp-proxy`.
- Do not require shell wrappers.
- Do not emit logs to stdout.
- Accept all runtime configuration through command args and env vars.

The examples below assume `mcp-proxy` is installed on `PATH`. If it is not, replace it with an absolute interpreter path or environment-specific launcher.

## Claude Code

Project-scoped example:

```json
{
  "mcpServers": {
    "proxy": {
      "type": "stdio",
      "command": "mcp-proxy",
      "args": ["--config", "/absolute/path/to/servers.json"],
      "env": {}
    }
  }
}
```

## Codex

CLI registration example:

```bash
codex mcp add proxy -- mcp-proxy --config /absolute/path/to/servers.json
```

Config example:

```toml
[mcp_servers.proxy]
command = "mcp-proxy"
args = ["--config", "/absolute/path/to/servers.json"]
```

## Cursor

Project-scoped example:

```json
{
  "mcpServers": {
    "proxy": {
      "type": "stdio",
      "command": "mcp-proxy",
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
      "command": ["mcp-proxy", "--config", "/absolute/path/to/servers.json"],
      "enabled": true
    }
  }
}
```
