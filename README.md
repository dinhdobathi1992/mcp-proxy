# mcp-proxy

Thin FastMCP-based proxy that exposes multiple downstream MCP servers as one front MCP server.

Python 3.10+ is the intended runtime baseline.

## Features

- **Multi-backend aggregation** — stdio and HTTP/SSE backends in one proxy
- **Config hot-reload** — watch `servers.json` for changes with `--watch`
- **Dynamic registration** — add/remove backends at runtime via MCP tools
- **Health monitoring** — periodic health checks with status reporting
- **API key auth** — secure HTTP front with `--auth-api-key`
- **Rate limiting** — protect against abuse with `--rate-limit`
- **Structured logging** — JSON log output with `--log-format json`
- **Metrics** — request counts, latency percentiles, error rates
- **Graceful shutdown** — clean SIGINT/SIGTERM handling
- **TLS support** — HTTPS with `--tls-cert` and `--tls-key`

## Installation

```bash
cd /path/to/mcp-proxy
uv sync
```

## Quickstart

Create a `servers.json` config with your downstream MCP servers:

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

Run commands from the project directory using `uv run`:

```bash
# Validate config
uv run mcp-proxy --config servers.json --check

# Run as stdio server (for Claude Code, Cursor, OpenCode)
uv run mcp-proxy --config servers.json

# Run with hot-reload
uv run mcp-proxy --config servers.json --watch

# Run as HTTP server
uv run mcp-proxy --config servers.json --transport http --port 8000

# Run as HTTP server with auth
uv run mcp-proxy --config servers.json --transport http --auth-api-key mysecret

# Run with JSON logging
uv run mcp-proxy --config servers.json --log-format json

# Run with TLS
uv run mcp-proxy --config servers.json --transport http --tls-cert cert.pem --tls-key key.pem
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `servers.json` | Path to downstream server config |
| `--transport` | `stdio` | Front transport: `stdio` or `http` |
| `--host` | `127.0.0.1` | Bind host for HTTP transport |
| `--port` | `8000` | Bind port for HTTP transport |
| `--name` | `mcp-proxy` | Name reported by front MCP server |
| `--log-level` | `INFO` | Logging level |
| `--log-format` | `text` | Log format: `text` or `json` |
| `--check` | — | Validate config and exit |
| `--watch` | — | Watch config for hot-reload |
| `--health-interval` | `30.0` | Health check interval (seconds) |
| `--auth-api-key` | — | API key for HTTP auth |
| `--rate-limit` | `100` | Requests per minute per IP |
| `--tls-cert` | — | TLS certificate path |
| `--tls-key` | — | TLS key path |
| `--strict-startup` | `true` | Fail fast for startup checks |
| `--ui-mode` | `off` | Management UI mode: `off`, `default`, `advanced` |
| `--ui-port` | `8080` | Management UI server port |

## Management Tools

When running, the proxy exposes these MCP tools:

- `proxy_list_backends` — list all backends with health status
- `proxy_add_backend` — add a backend at runtime
- `proxy_remove_backend` — remove a backend
- `proxy_enable_backend` / `proxy_disable_backend` — toggle backends
- `proxy_reload_config` — force config reload
- `proxy_health_status` — get health status
- `proxy_metrics` — get request metrics

## Management UI

The proxy includes an optional web-based management UI.

```bash
# Run with status dashboard (read-only)
uv run mcp-proxy --config servers.json --ui-mode default --ui-port 8080

# Run with full admin panel
uv run mcp-proxy --config servers.json --ui-mode advanced --ui-port 8080
```

Open http://localhost:8080 in your browser.

### UI Modes

- `off` — No UI, zero overhead (default)
- `default` — Status dashboard: backends, health, metrics
- `advanced` — Full admin: toggle backends, reload config, add/remove

### Performance

The UI runs as a separate process. The proxy writes status to a file every 2s (< 0.01ms overhead). When UI is `off`, there is zero overhead.

## Client Configuration

The proxy uses `.venv/bin/mcp-proxy` as the executable. Use the full path in your client config:

```json
{
  "mcpServers": {
    "proxy": {
      "command": "/absolute/path/to/mcp-proxy/.venv/bin/mcp-proxy",
      "args": ["--config", "/absolute/path/to/servers.json"]
    }
  }
}
```

Or use the install script to auto-configure clients:

```bash
./scripts/install-mcp-proxy.sh --opencode
./scripts/install-mcp-proxy.sh --claude
./scripts/install-mcp-proxy.sh --all
```

See `examples/` for client-specific config samples and `docs/client-compatibility.md` for detailed notes.

## Compatibility Notes

- Logs go to stderr (MCP stdout stays clean)
- `stdio` is the primary target for local host integration
- Example host configs live under `examples/`
- Additional host notes live in `docs/client-compatibility.md`
