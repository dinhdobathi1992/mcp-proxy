# Management UI Design

**Date:** 2026-05-01
**Branch:** `feat/proxy-enhancements`
**Constraint:** Zero impact on proxy performance when UI is disabled. Minimal impact when enabled.

## Overview

Add a web-based management UI to mcp-proxy with a `UI_mode` variable that controls complexity:

- `off` — No UI, zero overhead (default)
- `default` — Read-only status dashboard
- `advanced` — Full admin panel with actions

The UI runs as a **separate process** to completely isolate it from the proxy. Communication is via **memory-mapped file** (proxy writes status, UI reads) and **command file** (UI writes commands, proxy reads) for advanced mode.

## Architecture

```
┌─────────────────────┐   writes mmap    ┌─────────────────────┐
│  mcp-proxy process  │ ──────────────▶  │  /tmp/mcp-proxy-    │
│  (your MCP server)  │   every 2s       │  status.mmap        │
└─────────────────────┘                   └──────────┬──────────┘
                                                     │ reads (mmap)
┌─────────────────────┐   polls cmd file  ┌──────────▼──────────┐
│  mcp-proxy process  │ ◀───────────────  │  mcp-proxy-ui       │
│                     │   every 2s        │  (Python + Vue)     │
└─────────────────────┘                   │  port 8080          │
                                          │  WebSocket push     │
                                          └──────────┬──────────┘
                                                     │ WebSocket
                                          ┌──────────▼──────────┐
                                          │  Browser            │
                                          │  Vue 3 dashboard    │
                                          └─────────────────────┘
```

## UI Mode Configuration

### CLI Flag

```
--ui-mode off|default|advanced   (default: off)
```

| Mode | What it writes | Performance impact |
|------|---------------|-------------------|
| `off` | Nothing | Zero |
| `default` | Status snapshot to mmap every 2s | < 0.01ms per write |
| `advanced` | Status snapshot + polls command file | < 0.1ms per cycle |

### Additional CLI Flags

```
--ui-port 8080                          UI server port
--ui-status-path /tmp/mcp-proxy-status.mmap   Status file path
--ui-command-path /tmp/mcp-proxy-commands.jsonl  Command file path (advanced mode)
--ui-update-interval 2                  Status write interval (seconds)
```

## Data Flow

### Status Snapshot (proxy → UI)

The proxy writes a JSON-serialized status snapshot to a memory-mapped file every `--ui-update-interval` seconds.

**File:** `/tmp/mcp-proxy-status.mmap`

**Snapshot structure:**
```json
{
  "timestamp": "2026-05-01T18:00:00Z",
  "proxy_name": "mcp-proxy",
  "backends": [
    {
      "name": "atlassian",
      "transport": "stdio",
      "enabled": true,
      "health": "healthy",
      "requests": 42,
      "errors": 1,
      "latency_p50": 12.5,
      "latency_p95": 45.2,
      "latency_p99": 89.1
    }
  ],
  "totals": {
    "requests": 42,
    "errors": 1,
    "backends": 1,
    "healthy": 1,
    "unhealthy": 0
  }
}
```

### Command File (UI → proxy) — Advanced mode only

The UI writes commands to a JSONL file that the proxy polls.

**File:** `/tmp/mcp-proxy-commands.jsonl`

**Command structure:**
```json
{"id":"cmd-1","action":"disable_backend","args":{"name":"atlassian"},"timestamp":"2026-05-01T18:00:01Z"}
```

**Supported actions:**
- `enable_backend` — `{"name": "backend_name"}`
- `disable_backend` — `{"name": "backend_name"}`
- `reload_config` — `{}`
- `add_backend` — `{"name": "...", "command": "...", "args": [...]}`
- `remove_backend` — `{"name": "backend_name"}`

The proxy reads and processes commands on its next poll cycle. Processed commands are removed from the file. Invalid commands are logged and skipped.

**Concurrency:** The command file uses atomic writes (write to temp file, then rename). The proxy reads the entire file, processes all commands, then truncates it. If the proxy reads while the UI is writing, the rename ensures a consistent view.

## Proxy-Side Implementation

### New Modules

- `src/mcp_proxy/ui_writer.py` — Writes status snapshot to mmap
- `src/mcp_proxy/ui_reader.py` — Reads commands from command file (advanced mode)

### Integration with LifecycleManager

In `lifecycle.py`:
- If `ui_mode != "off"`: start a background thread that writes status to mmap every N seconds
- If `ui_mode == "advanced"`: start a background thread that polls the command file every N seconds
- Both threads are daemon threads (die with the process)

### mmap Write Logic

```python
def write_status_snapshot(path: str, data: dict) -> None:
    """Write JSON status to file. < 0.01ms."""
    payload = json.dumps(data).encode("utf-8")
    size = len(payload)
    with open(path, "wb") as f:
        f.write(struct.pack("<I", size))
        f.write(payload)
```

The UI server reads this file via mmap for zero-copy access. The proxy writes atomically (size prefix + payload in single write call).

## UI Server

### New Module

`src/mcp_proxy/ui_server.py` — Separate Python process that:
1. Reads the mmap status file
2. Serves the Vue SPA (static files)
3. Pushes updates to WebSocket clients
4. Receives commands from WebSocket (advanced mode)

### Dependencies

- `websockets` — lightweight WebSocket library
- No other new runtime deps

### Endpoints

- `GET /` — Serve Vue SPA
- `GET /ws` — WebSocket for real-time updates
- `GET /api/status` — REST fallback for status snapshot

### Startup

```bash
# Standalone
uv run mcp-proxy-ui --port 8080 --status-path /tmp/mcp-proxy-status.mmap

# Or auto-started by the proxy when --ui-mode is not off
mcp-proxy --config servers.json --ui-mode default --ui-port 8080
```

When `--ui-mode` is not `off`, the proxy spawns `mcp-proxy-ui` as a child process. If the child crashes, the proxy logs a warning but continues normally. The child process is killed on proxy shutdown.

## Vue 3 Frontend

### Project Structure

```
ui/
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── composables/
│   │   └── useWebSocket.ts
│   ├── components/
│   │   ├── StatusDashboard.vue
│   │   ├── BackendCard.vue
│   │   ├── MetricsChart.vue
│   │   └── AdminPanel.vue
│   └── types/
│       └── index.ts
```

### Default Mode (Status Dashboard)

- Backend list with health status (green/yellow/red indicators)
- Request counts per backend
- Latency percentiles (p50/p95/p99)
- Total proxy uptime
- Auto-refresh via WebSocket

### Advanced Mode (Admin Panel)

Adds to default mode:
- Enable/disable backend buttons
- Reload config button
- Add/remove backend forms
- Real-time log stream

### Tech Stack

- Vue 3 + TypeScript
- Vite for build
- Lightweight chart library (uPlot or Chart.js)
- No UI framework (custom CSS, small footprint)
- Total bundle: ~50KB gzipped

## Performance Isolation

### Proxy-side overhead (when UI is enabled):

- **mmap write:** Every 2s, serialize ~500 bytes JSON, memcpy to mmap. **< 0.01ms**
- **Command file poll:** Every 2s, read a small file. **< 0.1ms** (only in advanced mode)
- **No threads added to request path:** mmap write happens in the existing lifecycle manager loop
- **No network calls:** Everything is file-based

### UI server overhead:

- **Runs in a separate process** — completely isolated
- **Reads mmap** — zero-copy read from shared memory
- **WebSocket push** — only when data changes
- **Static file serving** — Vue bundle is ~50KB gzipped

### Failures are contained:

- If UI server crashes → proxy continues normally
- If mmap file is corrupted → UI shows stale data, proxy unaffected
- If command file has bad JSON → proxy logs warning, skips it
- If UI mode is `off` → zero overhead, no mmap writes at all

### Benchmarking:

Add `--ui-benchmark` flag that logs mmap write duration to verify < 0.01ms overhead.

## File Tree (New)

```
src/mcp_proxy/
├── ui_writer.py        (NEW: writes status to mmap)
├── ui_reader.py        (NEW: reads commands from file)
└── ui_server.py        (NEW: serves Vue SPA + WebSocket)

ui/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.ts
    ├── App.vue
    ├── composables/useWebSocket.ts
    ├── components/
    │   ├── StatusDashboard.vue
    │   ├── BackendCard.vue
    │   ├── MetricsChart.vue
    │   └── AdminPanel.vue
    └── types/index.ts
```

## Implementation Order

1. `ui_writer.py` — mmap status writer (proxy side)
2. `ui_reader.py` — command file reader (proxy side)
3. `lifecycle.py` integration — background threads for UI
4. Vue project scaffold — Vite + TypeScript setup
5. Status dashboard components (default mode)
6. Admin panel components (advanced mode)
7. `ui_server.py` — Python WebSocket server
8. CLI integration — `--ui-mode` flag
9. Auto-start UI server from proxy
10. Tests and documentation
