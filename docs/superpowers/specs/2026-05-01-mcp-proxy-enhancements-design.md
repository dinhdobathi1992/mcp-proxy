# mcp-proxy Enhancements Design

**Date:** 2026-05-01
**Branch:** `feat/proxy-enhancements`
**Approach:** Layered Enhancement (keep FastMCP `create_proxy()`, add management layers)

## Overview

Enhance mcp-proxy from a thin config shell into a full-featured centralized MCP proxy with:

- Config hot-reload (watch `servers.json` for changes)
- Dynamic backend registration via MCP tools
- Health checks and retry/reconnect
- Authentication and rate limiting on HTTP front
- Structured logging and metrics
- Graceful shutdown
- Gap fixes (stale README, missing validation, missing tests)

## Architecture

```
MCP Host (Claude/Cursor/OpenCode)
        │
        ▼
┌───────────────────────────────────┐
│         mcp-proxy process         │
│                                   │
│  ┌─────────────────────────────┐  │
│  │     CLI (cli.py)            │  │
│  │     Config Loader           │  │
│  └──────────┬──────────────────┘  │
│             │                     │
│  ┌──────────▼──────────────────┐  │
│  │  ProxyLifecycleManager      │  │
│  │  - owns FastMCP proxy ref   │  │
│  │  - config file watcher      │  │
│  │  - health checker           │  │
│  │  - rebuilds proxy on change │  │
│  └──────────┬──────────────────┘  │
│             │                     │
│  ┌──────────▼──────────────────┐  │
│  │  FastMCP create_proxy()     │  │
│  │  - protocol handling        │  │
│  │  - tool/prompt routing      │  │
│  └──────────┬──────────────────┘  │
│             │                     │
│  ┌──────────▼──────────────────┐  │
│  │  Management Tools (MCP)     │  │
│  │  - proxy_list_backends      │  │
│  │  - proxy_add_backend        │  │
│  │  - proxy_remove_backend     │  │
│  │  - proxy_reload_config      │  │
│  │  - proxy_health_status      │  │
│  │  - proxy_metrics            │  │
│  └─────────────────────────────┘  │
└───────────────────────────────────┘
        │
        ▼
  N downstream MCP servers
```

## New Modules

### `src/mcp_proxy/lifecycle.py` — ProxyLifecycleManager

Central orchestrator that owns the FastMCP proxy instance and coordinates all subsystems.

**Class: `ProxyLifecycleManager`**
- `__init__(config_path, name, strict_startup, watch, health_interval, max_retries, retry_backoff)`
- `start()` — Initial proxy build, start health checker, start config watcher (if enabled)
- `stop()` — Graceful shutdown: stop watcher, stop health checker, close backends
- `rebuild_proxy()` — Re-read config, validate, diff against current, rebuild FastMCP proxy
- `get_proxy()` — Returns current proxy instance (thread-safe via `threading.Lock`)
- `get_config()` — Returns current `ProxyConfig`

**Config Watcher:**
- Uses `watchdog` library for filesystem events on `servers.json`
- Debounces changes (500ms) to avoid rapid rebuilds
- On change: re-validate config, log diff, rebuild proxy
- On validation error: log warning, keep current config (never break running state)
- Fallback: polling every 5s if `watchdog` unavailable

### `src/mcp_proxy/health.py` — Health Checker

Background task that monitors backend health.

**Class: `HealthChecker`**
- `__init__(backends, interval, on_status_change)`
- `start()` — Begin periodic health checks
- `stop()` — Stop health checks
- `get_status(backend_name)` — Returns `healthy | unhealthy | unknown`
- `get_all_status()` — Returns dict of all backend statuses

**Check method:**
- Stdio backends: send MCP `ping` request via the subprocess
- HTTP backends: send MCP `ping` request via HTTP client
- Timeout: 5s per check
- State tracking: `healthy` (ping succeeded), `unhealthy` (ping failed), `unknown` (not yet checked)

**Retry/Reconnect interaction:**
- Retry logic lives in the request path (not in health checker). When a request to a backend fails, retry up to `--max-retries` times with exponential backoff.
- Health checker independently monitors backend availability. A backend marked `unhealthy` by health checker will still receive requests (with retry). The health status is informational for `proxy_list_backends` and `proxy_health_status` tools.
- Stdio backend crash recovery: if a stdio subprocess exits, `ProxyLifecycleManager` restarts it (up to 5 times in 60s). This is separate from health checker — it's event-driven, not polling.

### `src/mcp_proxy/management.py` — MCP Management Tools

Tools exposed on the proxy itself, prefixed with `proxy_` to avoid namespace collisions.

**Integration with FastMCP:** Management tools are registered as MCP tools on the proxy via `fastmcp.tool()` decorator. They are added to the proxy instance after `create_proxy()` returns. When the proxy is rebuilt on config change, management tools are re-registered on the new instance. This means management tools are always available even when backends change.

| Tool | Parameters | Returns |
|------|-----------|---------|
| `proxy_list_backends` | — | List of backends with name, transport, enabled, health status |
| `proxy_add_backend` | `name: str`, `command?: str`, `url?: str`, `args?: list`, `env?: dict`, `headers?: dict`, `persist?: bool` | Success/error message |
| `proxy_remove_backend` | `name: str`, `persist?: bool` | Success/error message |
| `proxy_enable_backend` | `name: str`, `persist?: bool` | Success/error message |
| `proxy_disable_backend` | `name: str`, `persist?: bool` | Success/error message |
| `proxy_reload_config` | — | List of changes detected |
| `proxy_health_status` | — | Health status of all backends |
| `proxy_metrics` | — | Request counts, latency, errors |

**Persistence:** When `persist=True`, changes are written to `servers.json`. Default is `False` (runtime-only).

### `src/mcp_proxy/auth.py` — Authentication & Rate Limiting

**API Key Auth:**
- CLI flag: `--auth-api-key <key>` or env var `MCP_PROXY_API_KEY`
- Middleware validates `Authorization: Bearer <key>` header
- Returns 401 on missing/invalid key
- Only applies to HTTP front transport

**Rate Limiting:**
- CLI flag: `--rate-limit <requests-per-minute>` (default: 100)
- In-memory sliding window per client IP
- Returns 429 with `Retry-After` header
- Only applies to HTTP front transport

**TLS:**
- CLI flags: `--tls-cert <path>`, `--tls-key <path>`
- If provided, proxy listens on HTTPS
- Useful for team deployments

### `src/mcp_proxy/metrics.py` — In-Memory Metrics

**Class: `Metrics`**
- `record_request(backend_name, duration_ms, success)`
- `get_metrics()` — Returns dict with all counters and percentiles

**Counters:**
- `requests_total` — total requests received
- `requests_per_backend` — dict of backend_name → count
- `errors_total` — total errors
- `backend_latency_ms` — dict of backend_name → {p50, p95, p99}
- `backend_health` — dict of backend_name → 1 (healthy) / 0 (unhealthy)

Exposed via `proxy_metrics` MCP tool.

## CLI Changes

New flags added to `cli.py`:

| Flag | Default | Description |
|------|---------|-------------|
| `--watch` | off | Enable config file hot-reload |
| `--health-interval` | 30 | Health check interval in seconds |
| `--max-retries` | 3 | Max retries on backend failure |
| `--retry-backoff` | 0.1 | Initial retry backoff in seconds |
| `--auth-api-key` | none | API key for HTTP front auth |
| `--rate-limit` | 100 | Requests per minute per IP |
| `--tls-cert` | none | TLS certificate path |
| `--tls-key` | none | TLS key path |
| `--log-format` | text | Log format: `text` or `json` |

## Graceful Shutdown

Signal handling in `cli.py`:
1. Catch `SIGINT` and `SIGTERM`
2. Call `lifecycle_manager.stop()`
3. Stop accepting new requests
4. Wait for in-flight requests (max 10s timeout)
5. Close all backend connections
6. Exit with code 0

## Config Validation Additions

`validate.py` additions:
- `cwd` field: optional string, must be an existing directory
- No other schema changes (management tools handle runtime additions)

## Gap Fixes

1. **README.md** — Remove reference to deleted `REPO_PLAN.md`, document new features
2. **Resource tests** — Add tests for MCP resource aggregation
3. **`cwd` validation** — Explicit validation in `validate.py`

## New Dependencies

- `watchdog>=4.0.0` — filesystem watching for hot-reload

## Testing Strategy

### Unit Tests
- `test_lifecycle.py` — ProxyLifecycleManager: start, stop, rebuild, config diff
- `test_health.py` — HealthChecker: ping success/failure, state transitions
- `test_management.py` — Management tools: add/remove/enable/disable backends
- `test_auth.py` — API key validation, rate limiting
- `test_metrics.py` — Counter increments, percentile calculations

### Integration Tests
- Hot-reload: modify config file, verify proxy picks up changes
- Management tools: add backend at runtime, verify tools appear
- Health check: mock backend going unhealthy, verify status reported
- Auth: send requests with/without API key, verify 401/200
- Graceful shutdown: send SIGTERM, verify clean exit

## File Tree (New)

```
src/mcp_proxy/
├── __init__.py
├── cli.py              (modified: new flags, signal handling)
├── config.py           (minor: cwd validation)
├── logging.py          (modified: structured JSON format)
├── server.py           (modified: use ProxyLifecycleManager)
├── validate.py         (modified: cwd validation)
├── lifecycle.py        (NEW)
├── health.py           (NEW)
├── management.py       (NEW)
├── auth.py             (NEW)
└── metrics.py          (NEW)
```

## Implementation Order

1. Gap fixes (README, cwd validation, resource tests)
2. Structured logging
3. Metrics
4. Graceful shutdown
5. Health checker
6. Retry/reconnect
7. Config hot-reload (lifecycle manager)
8. Management tools
9. Auth & rate limiting
10. TLS support
