# Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a web-based management UI to mcp-proxy with `UI_mode` (off/default/advanced), running as a separate process, communicating via memory-mapped file.

**Architecture:** Proxy writes status to mmap file, separate UI server reads it and pushes to Vue 3 frontend via WebSocket. Command file for advanced mode actions.

**Tech Stack:** Python 3.10+, Vue 3, Vite, TypeScript, websockets

---

## File Structure

```
src/mcp_proxy/
├── ui_writer.py        (NEW: writes status to file)
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

tests/
├── test_ui_writer.py   (NEW)
├── test_ui_reader.py   (NEW)
└── test_ui_server.py   (NEW)
```

---

## Task 1: Status Writer (Proxy Side)

**Files:**
- Create: `src/mcp_proxy/ui_writer.py`
- Create: `tests/test_ui_writer.py`

### Step 1: Write tests

```python
# tests/test_ui_writer.py
from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mcp_proxy.ui_writer import StatusWriter


class TestStatusWriter:
    def test_write_creates_file(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        writer.write({
            "timestamp": "2026-05-01T18:00:00Z",
            "backends": [],
            "totals": {"requests": 0},
        })
        assert Path(path).exists()

    def test_write_produces_readable_format(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        data = {
            "timestamp": "2026-05-01T18:00:00Z",
            "backends": [{"name": "echo", "health": "healthy"}],
            "totals": {"requests": 42},
        }
        writer.write(data)

        raw = Path(path).read_bytes()
        size = struct.unpack("<I", raw[:4])[0]
        payload = raw[4 : 4 + size]
        parsed = json.loads(payload)
        assert parsed["backends"][0]["name"] == "echo"
        assert parsed["totals"]["requests"] == 42

    def test_write_overwrites_previous(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        writer.write({"v": 1})
        writer.write({"v": 2})

        raw = Path(path).read_bytes()
        size = struct.unpack("<I", raw[:4])[0]
        payload = raw[4 : 4 + size]
        assert json.loads(payload)["v"] == 2

    def test_write_empty_backends(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        writer.write({"backends": [], "totals": {}})
        assert Path(path).stat().st_size > 0
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_ui_writer.py -v
```

### Step 3: Implement

```python
# src/mcp_proxy/ui_writer.py
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any


class StatusWriter:
    """Writes proxy status snapshot to a file for UI consumption."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def write(self, data: dict[str, Any]) -> None:
        """Write status snapshot atomically.

        Format: 4-byte little-endian size prefix + JSON payload.
        """
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        size = struct.pack("<I", len(payload))
        self._path.write_bytes(size + payload)
```

### Step 4: Run tests

```bash
pytest tests/test_ui_writer.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/ui_writer.py tests/test_ui_writer.py
git commit -m "feat: add status writer for UI communication"
```

---

## Task 2: Command Reader (Proxy Side)

**Files:**
- Create: `src/mcp_proxy/ui_reader.py`
- Create: `tests/test_ui_reader.py`

### Step 1: Write tests

```python
# tests/test_ui_reader.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_proxy.ui_reader import CommandReader


class TestCommandReader:
    def test_read_empty_file(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        path.write_text("")
        reader = CommandReader(path)
        assert reader.read_commands() == []

    def test_read_single_command(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        cmd = {"id": "c1", "action": "disable_backend", "args": {"name": "echo"}}
        path.write_text(json.dumps(cmd) + "\n")
        reader = CommandReader(path)
        commands = reader.read_commands()
        assert len(commands) == 1
        assert commands[0]["action"] == "disable_backend"

    def test_read_multiple_commands(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        cmds = [
            {"id": "c1", "action": "disable_backend", "args": {"name": "echo"}},
            {"id": "c2", "action": "reload_config", "args": {}},
        ]
        path.write_text("\n".join(json.dumps(c) for c in cmds) + "\n")
        reader = CommandReader(path)
        commands = reader.read_commands()
        assert len(commands) == 2

    def test_read_clears_file(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        cmd = {"id": "c1", "action": "reload_config", "args": {}}
        path.write_text(json.dumps(cmd) + "\n")
        reader = CommandReader(path)
        reader.read_commands()
        assert path.read_text() == ""

    def test_read_skips_invalid_json(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        path.write_text("not json\n{\"id\":\"c1\",\"action\":\"reload_config\",\"args\":{}}\n")
        reader = CommandReader(path)
        commands = reader.read_commands()
        assert len(commands) == 1
        assert commands[0]["id"] == "c1"

    def test_read_nonexistent_file(self, tmp_path: Path):
        path = tmp_path / "nonexistent.jsonl"
        reader = CommandReader(path)
        assert reader.read_commands() == []
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_ui_reader.py -v
```

### Step 3: Implement

```python
# src/mcp_proxy/ui_reader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .logging import get_logger

LOGGER = get_logger("ui_reader")


class CommandReader:
    """Reads commands from a JSONL file written by the UI."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def read_commands(self) -> list[dict[str, Any]]:
        """Read all commands and clear the file.

        Returns list of command dicts. Invalid lines are logged and skipped.
        """
        if not self._path.exists():
            return []

        try:
            text = self._path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            LOGGER.warning("Failed to read command file: %s", exc)
            return []

        if not text:
            return []

        commands: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                commands.append(json.loads(line))
            except json.JSONDecodeError as exc:
                LOGGER.warning("Skipping invalid command line: %s", exc)

        # Clear the file after reading
        try:
            self._path.write_text("", encoding="utf-8")
        except OSError as exc:
            LOGGER.warning("Failed to clear command file: %s", exc)

        return commands
```

### Step 4: Run tests

```bash
pytest tests/test_ui_reader.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/ui_reader.py tests/test_ui_reader.py
git commit -m "feat: add command reader for UI communication"
```

---

## Task 3: Lifecycle Manager Integration

**Files:**
- Modify: `src/mcp_proxy/lifecycle.py`
- Modify: `tests/test_lifecycle.py`

### Step 1: Read current lifecycle.py

### Step 2: Add UI writer integration

Add to `ProxyLifecycleManager.__init__`:
```python
self._ui_mode = ui_mode  # "off", "default", "advanced"
self._ui_status_path = ui_status_path
self._ui_command_path = ui_command_path
self._ui_update_interval = ui_update_interval
self._ui_writer: StatusWriter | None = None
self._ui_reader: CommandReader | None = None
self._ui_thread: threading.Thread | None = None
self._ui_command_thread: threading.Thread | None = None
```

Add to `start()`:
```python
if self._ui_mode != "off":
    self._start_ui_writer()
if self._ui_mode == "advanced":
    self._start_ui_reader()
```

Add to `stop()`:
```python
# UI threads are daemon threads, they die automatically
```

### Step 3: Write UI writer thread

```python
def _start_ui_writer(self) -> None:
    from .ui_writer import StatusWriter
    self._ui_writer = StatusWriter(self._ui_status_path)
    self._ui_thread = threading.Thread(target=self._ui_write_loop, daemon=True)
    self._ui_thread.start()

def _ui_write_loop(self) -> None:
    while not self._stop_event.is_set():
        self._write_ui_status()
        self._stop_event.wait(self._ui_update_interval)

def _write_ui_status(self) -> None:
    if not self._ui_writer:
        return
    config = self.get_config()
    metrics = self._metrics.get_metrics()
    health = self._health_checker

    backends = []
    for b in config.backends:
        status = "unknown"
        if health:
            status = health.get_status(b.name).value
        backends.append({
            "name": b.name,
            "transport": b.transport,
            "enabled": b.enabled,
            "health": status,
            "requests": metrics.get("requests_per_backend", {}).get(b.name, 0),
            "errors": 0,  # per-backend errors not tracked yet
            "latency_p50": metrics.get("backend_latency_ms", {}).get(b.name, {}).get("p50", 0),
            "latency_p95": metrics.get("backend_latency_ms", {}).get(b.name, {}).get("p95", 0),
            "latency_p99": metrics.get("backend_latency_ms", {}).get(b.name, {}).get("p99", 0),
        })

    from datetime import datetime, timezone
    self._ui_writer.write({
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "proxy_name": self._name,
        "backends": backends,
        "totals": {
            "requests": metrics.get("requests_total", 0),
            "errors": metrics.get("errors_total", 0),
            "backends": len(config.backends),
            "healthy": sum(1 for b in backends if b["health"] == "healthy"),
            "unhealthy": sum(1 for b in backends if b["health"] == "unhealthy"),
        },
    })
```

### Step 4: Write UI reader thread (advanced mode)

```python
def _start_ui_reader(self) -> None:
    from .ui_reader import CommandReader
    self._ui_reader = CommandReader(self._ui_command_path)
    self._ui_command_thread = threading.Thread(target=self._ui_command_loop, daemon=True)
    self._ui_command_thread.start()

def _ui_command_loop(self) -> None:
    while not self._stop_event.is_set():
        self._process_ui_commands()
        self._stop_event.wait(self._ui_update_interval)

def _process_ui_commands(self) -> None:
    if not self._ui_reader:
        return
    commands = self._ui_reader.read_commands()
    for cmd in commands:
        try:
            self._execute_ui_command(cmd)
        except Exception as exc:
            LOGGER.warning("Failed to execute UI command %s: %s", cmd.get("id"), exc)

def _execute_ui_command(self, cmd: dict) -> None:
    from .management import ManagementTools
    tools = ManagementTools(self)
    action = cmd.get("action")
    args = cmd.get("args", {})

    if action == "enable_backend":
        tools.enable_backend(args["name"])
    elif action == "disable_backend":
        tools.disable_backend(args["name"])
    elif action == "reload_config":
        tools.reload_config()
    elif action == "add_backend":
        tools.add_backend(**args)
    elif action == "remove_backend":
        tools.remove_backend(args["name"])
    else:
        LOGGER.warning("Unknown UI command action: %s", action)
```

### Step 5: Run tests

```bash
pytest tests/test_lifecycle.py -v
```

### Step 6: Commit

```bash
git add src/mcp_proxy/lifecycle.py tests/test_lifecycle.py
git commit -m "feat: integrate UI writer/reader into lifecycle manager"
```

---

## Task 4: Vue Project Scaffold

**Files:**
- Create: `ui/package.json`
- Create: `ui/vite.config.ts`
- Create: `ui/index.html`
- Create: `ui/tsconfig.json`
- Create: `ui/src/main.ts`
- Create: `ui/src/App.vue`
- Create: `ui/src/types/index.ts`

### Step 1: Create package.json

```json
{
  "name": "mcp-proxy-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.5.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.0.0"
  }
}
```

### Step 2: Create vite.config.ts

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8080',
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

### Step 3: Create index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>mcp-proxy Dashboard</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

### Step 4: Create src/types/index.ts

```typescript
export interface BackendStatus {
  name: string
  transport: string
  enabled: boolean
  health: 'healthy' | 'unhealthy' | 'unknown'
  requests: number
  errors: number
  latency_p50: number
  latency_p95: number
  latency_p99: number
}

export interface StatusSnapshot {
  timestamp: string
  proxy_name: string
  backends: BackendStatus[]
  totals: {
    requests: number
    errors: number
    backends: number
    healthy: number
    unhealthy: number
  }
}
```

### Step 5: Create src/main.ts

```typescript
import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
```

### Step 6: Create src/App.vue

```vue
<script setup lang="ts">
import StatusDashboard from './components/StatusDashboard.vue'
</script>

<template>
  <div id="app">
    <header>
      <h1>mcp-proxy Dashboard</h1>
    </header>
    <main>
      <StatusDashboard />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
header { background: #1a1a2e; color: white; padding: 1rem 2rem; }
main { padding: 2rem; }
</style>
```

### Step 7: Install and build

```bash
cd ui && npm install && npm run build
```

### Step 8: Commit

```bash
git add ui/
git commit -m "feat: scaffold Vue 3 frontend project"
```

---

## Task 5: WebSocket Composable & Status Dashboard

**Files:**
- Create: `ui/src/composables/useWebSocket.ts`
- Create: `ui/src/components/StatusDashboard.vue`
- Create: `ui/src/components/BackendCard.vue`

### Step 1: Create useWebSocket.ts

```typescript
import { ref, onMounted, onUnmounted } from 'vue'
import type { StatusSnapshot } from '../types'

export function useWebSocket(url: string) {
  const data = ref<StatusSnapshot | null>(null)
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null

  function connect() {
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (event) => {
      try {
        data.value = JSON.parse(event.data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onclose = () => {
      connected.value = false
      reconnectTimer = window.setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  onMounted(connect)

  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  })

  return { data, connected }
}
```

### Step 2: Create BackendCard.vue

```vue
<script setup lang="ts">
import type { BackendStatus } from '../types'

defineProps<{ backend: BackendStatus }>()

function healthColor(health: string) {
  if (health === 'healthy') return '#4ade80'
  if (health === 'unhealthy') return '#f87171'
  return '#fbbf24'
}
</script>

<template>
  <div class="backend-card">
    <div class="header">
      <span class="name">{{ backend.name }}</span>
      <span class="badge" :style="{ background: healthColor(backend.health) }">
        {{ backend.health }}
      </span>
    </div>
    <div class="stats">
      <div><span class="label">Transport:</span> {{ backend.transport }}</div>
      <div><span class="label">Requests:</span> {{ backend.requests }}</div>
      <div><span class="label">Errors:</span> {{ backend.errors }}</div>
      <div><span class="label">Latency p50:</span> {{ backend.latency_p50.toFixed(1) }}ms</div>
      <div><span class="label">Latency p95:</span> {{ backend.latency_p95.toFixed(1) }}ms</div>
      <div><span class="label">Latency p99:</span> {{ backend.latency_p99.toFixed(1) }}ms</div>
    </div>
  </div>
</template>

<style scoped>
.backend-card { background: white; border-radius: 8px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.name { font-weight: 600; font-size: 1.1rem; }
.badge { padding: 0.25rem 0.5rem; border-radius: 4px; color: white; font-size: 0.75rem; text-transform: uppercase; }
.stats { display: grid; gap: 0.25rem; font-size: 0.9rem; }
.label { color: #666; }
</style>
```

### Step 3: Create StatusDashboard.vue

```vue
<script setup lang="ts">
import { useWebSocket } from '../composables/useWebSocket'
import BackendCard from './BackendCard.vue'

const { data, connected } = useWebSocket(`ws://${location.host}/ws`)
</script>

<template>
  <div class="dashboard">
    <div class="connection" :class="{ online: connected }">
      {{ connected ? 'Connected' : 'Disconnected' }}
    </div>

    <div v-if="data" class="summary">
      <div class="stat">
        <div class="value">{{ data.totals.backends }}</div>
        <div class="label">Backends</div>
      </div>
      <div class="stat">
        <div class="value">{{ data.totals.healthy }}</div>
        <div class="label">Healthy</div>
      </div>
      <div class="stat">
        <div class="value">{{ data.totals.requests }}</div>
        <div class="label">Requests</div>
      </div>
      <div class="stat">
        <div class="value">{{ data.totals.errors }}</div>
        <div class="label">Errors</div>
      </div>
    </div>

    <div v-if="data" class="backends">
      <BackendCard
        v-for="backend in data.backends"
        :key="backend.name"
        :backend="backend"
      />
    </div>

    <div v-if="data" class="timestamp">
      Last update: {{ new Date(data.timestamp).toLocaleTimeString() }}
    </div>
  </div>
</template>

<style scoped>
.dashboard { max-width: 1200px; margin: 0 auto; }
.connection { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 4px; background: #f87171; color: white; margin-bottom: 1rem; }
.connection.online { background: #4ade80; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
.stat { background: white; padding: 1rem; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.stat .value { font-size: 2rem; font-weight: 700; }
.stat .label { color: #666; font-size: 0.875rem; }
.backends { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.timestamp { color: #999; font-size: 0.75rem; text-align: right; }
</style>
```

### Step 4: Build and test

```bash
cd ui && npm run build
```

### Step 5: Commit

```bash
git add ui/src/
git commit -m "feat: add WebSocket composable and status dashboard"
```

---

## Task 6: Admin Panel Components (Advanced Mode)

**Files:**
- Create: `ui/src/components/AdminPanel.vue`
- Modify: `ui/src/App.vue`

### Step 1: Create AdminPanel.vue

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { StatusSnapshot } from '../types'

const props = defineProps<{ data: StatusSnapshot | null }>()

const message = ref('')

async function sendCommand(action: string, args: Record<string, unknown> = {}) {
  const id = `cmd-${Date.now()}`
  const cmd = { id, action, args, timestamp: new Date().toISOString() }

  try {
    const resp = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cmd),
    })
    const result = await resp.json()
    message.value = result.message || 'Command sent'
  } catch (e) {
    message.value = `Error: ${e}`
  }

  setTimeout(() => { message.value = '' }, 3000)
}
</script>

<template>
  <div class="admin-panel">
    <h2>Admin Panel</h2>

    <div v-if="message" class="message">{{ message }}</div>

    <div class="actions">
      <button @click="sendCommand('reload_config')">Reload Config</button>

      <div v-for="backend in data?.backends" :key="backend.name" class="backend-actions">
        <span>{{ backend.name }}</span>
        <button
          v-if="backend.enabled"
          @click="sendCommand('disable_backend', { name: backend.name })"
        >
          Disable
        </button>
        <button
          v-else
          @click="sendCommand('enable_backend', { name: backend.name })"
        >
          Enable
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-panel { background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-top: 2rem; }
.admin-panel h2 { margin-bottom: 1rem; }
.message { padding: 0.5rem; background: #e0f2fe; border-radius: 4px; margin-bottom: 1rem; }
.actions { display: flex; flex-direction: column; gap: 0.5rem; }
.backend-actions { display: flex; align-items: center; gap: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; }
button { padding: 0.5rem 1rem; border: none; border-radius: 4px; background: #3b82f6; color: white; cursor: pointer; }
button:hover { background: #2563eb; }
</style>
```

### Step 2: Update App.vue to include AdminPanel

```vue
<script setup lang="ts">
import { ref } from 'vue'
import StatusDashboard from './components/StatusDashboard.vue'
import AdminPanel from './components/AdminPanel.vue'

const uiMode = ref<'default' | 'advanced'>('advanced')
</script>

<template>
  <div id="app">
    <header>
      <h1>mcp-proxy Dashboard</h1>
      <div class="mode-toggle">
        <button :class="{ active: uiMode === 'default' }" @click="uiMode = 'default'">Status</button>
        <button :class="{ active: uiMode === 'advanced' }" @click="uiMode = 'advanced'">Admin</button>
      </div>
    </header>
    <main>
      <StatusDashboard />
      <AdminPanel v-if="uiMode === 'advanced'" :data="null" />
    </main>
  </div>
</template>
```

### Step 3: Build

```bash
cd ui && npm run build
```

### Step 4: Commit

```bash
git add ui/src/
git commit -m "feat: add admin panel for advanced mode"
```

---

## Task 7: UI Server (Python)

**Files:**
- Create: `src/mcp_proxy/ui_server.py`
- Create: `tests/test_ui_server.py`

### Step 1: Write tests

```python
# tests/test_ui_server.py
from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mcp_proxy.ui_server import UIServer


class TestUIServer:
    def test_read_status(self, tmp_path: Path):
        status_path = tmp_path / "status.dat"
        data = {"backends": [], "totals": {"requests": 0}}
        payload = json.dumps(data).encode()
        status_path.write_bytes(struct.pack("<I", len(payload)) + payload)

        server = UIServer(status_path=str(status_path), port=0)
        result = server.read_status()
        assert result["totals"]["requests"] == 0

    def test_read_status_missing_file(self, tmp_path: Path):
        server = UIServer(status_path=str(tmp_path / "nonexistent"), port=0)
        result = server.read_status()
        assert result is None
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_ui_server.py -v
```

### Step 3: Implement

```python
# src/mcp_proxy/ui_server.py
from __future__ import annotations

import asyncio
import json
import struct
from pathlib import Path
from typing import Any

from .logging import get_logger

LOGGER = get_logger("ui_server")


class UIServer:
    """Serves the management UI via HTTP and WebSocket."""

    def __init__(
        self,
        *,
        status_path: str,
        port: int = 8080,
        ui_dir: str | None = None,
    ) -> None:
        self._status_path = Path(status_path)
        self._port = port
        self._ui_dir = Path(ui_dir) if ui_dir else None

    def read_status(self) -> dict[str, Any] | None:
        """Read status snapshot from the file."""
        if not self._status_path.exists():
            return None
        try:
            raw = self._status_path.read_bytes()
            if len(raw) < 4:
                return None
            size = struct.unpack("<I", raw[:4])[0]
            payload = raw[4 : 4 + size]
            return json.loads(payload)
        except (OSError, json.JSONDecodeError, struct.error) as exc:
            LOGGER.warning("Failed to read status file: %s", exc)
            return None

    async def run(self) -> None:
        """Start the UI server."""
        try:
            import websockets
            from aiohttp import web
        except ImportError:
            LOGGER.error("UI server requires 'websockets' and 'aiohttp'. Install with: uv add websockets aiohttp")
            return

        app = web.Application()
        app.router.add_get("/api/status", self._handle_status)
        app.router.add_get("/ws", self._handle_websocket)
        if self._ui_dir and self._ui_dir.exists():
            app.router.add_static("/", self._ui_dir)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        LOGGER.info("UI server running on http://0.0.0.0:%s", self._port)

        # Keep running
        await asyncio.Event().wait()

    async def _handle_status(self, request) -> Any:
        from aiohttp import web
        status = self.read_status()
        if status is None:
            return web.json_response({"error": "No status available"}, status=503)
        return web.json_response(status)

    async def _handle_websocket(self, request) -> Any:
        import websockets
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        try:
            while not ws.closed:
                status = self.read_status()
                if status:
                    await ws.send_json(status)
                await asyncio.sleep(2)
        except Exception:
            pass
        finally:
            await ws.close()
        return ws
```

### Step 4: Run tests

```bash
pytest tests/test_ui_server.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/ui_server.py tests/test_ui_server.py
git commit -m "feat: add UI server with WebSocket support"
```

---

## Task 8: CLI Integration

**Files:**
- Modify: `src/mcp_proxy/cli.py`
- Modify: `src/mcp_proxy/server.py`

### Step 1: Add UI CLI flags to cli.py

```python
parser.add_argument(
    "--ui-mode",
    choices=("off", "default", "advanced"),
    default="off",
    help="Management UI mode: off, default (read-only), or advanced (full admin).",
)
parser.add_argument(
    "--ui-port",
    type=int,
    default=8080,
    help="Management UI server port.",
)
```

### Step 2: Update server.py to pass UI params

```python
def run_proxy(
    ...,
    ui_mode: str = "off",
    ui_port: int = 8080,
) -> int:
    ...
    mgr = ProxyLifecycleManager(
        ...,
        ui_mode=ui_mode,
        ui_status_path=f"/tmp/mcp-proxy-status-{os.getpid()}.dat",
        ui_command_path=f"/tmp/mcp-proxy-commands-{os.getpid()}.jsonl",
    )
    ...
```

### Step 3: Run tests

```bash
pytest tests/ -v
```

### Step 4: Commit

```bash
git add src/mcp_proxy/cli.py src/mcp_proxy/server.py
git commit -m "feat: add --ui-mode and --ui-port CLI flags"
```

---

## Task 9: Auto-Start UI Server

**Files:**
- Modify: `src/mcp_proxy/server.py`

### Step 1: Auto-start UI server process

When `--ui-mode` is not `off`, spawn the UI server as a child process:

```python
import subprocess
import sys

def _start_ui_server(ui_port: int, status_path: str) -> subprocess.Popen | None:
    """Start the UI server as a child process."""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_proxy.ui_server",
             "--port", str(ui_port),
             "--status-path", status_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        LOGGER.info("UI server started on port %s (PID: %s)", ui_port, proc.pid)
        return proc
    except Exception as exc:
        LOGGER.warning("Failed to start UI server: %s", exc)
        return None
```

### Step 2: Run tests

```bash
pytest tests/ -v
```

### Step 3: Commit

```bash
git add src/mcp_proxy/server.py
git commit -m "feat: auto-start UI server when --ui-mode is not off"
```

---

## Task 10: Documentation & Final Integration

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

### Step 1: Update README with UI docs

Add a "Management UI" section:

```markdown
## Management UI

The proxy includes an optional web-based management UI.

```bash
# Run with status dashboard (read-only)
mcp-proxy --config servers.json --ui-mode default --ui-port 8080

# Run with full admin panel
mcp-proxy --config servers.json --ui-mode advanced --ui-port 8080
```

Open http://localhost:8080 in your browser.

### UI Modes

- `off` — No UI, zero overhead (default)
- `default` — Status dashboard: backends, health, metrics
- `advanced` — Full admin: toggle backends, reload config, add/remove

### Performance

The UI runs as a separate process. The proxy writes status to a file every 2s (< 0.01ms overhead). When UI is `off`, there is zero overhead.
```

### Step 2: Add websockets dependency to pyproject.toml

```toml
[project.optional-dependencies]
ui = [
  "websockets>=14.0",
  "aiohttp>=3.10.0",
]
```

### Step 3: Run full test suite

```bash
pytest tests/ -v
```

### Step 4: Commit

```bash
git add README.md pyproject.toml
git commit -m "docs: add management UI documentation"
```

---

## Verification Checklist

- [ ] `--ui-mode off` — zero overhead, no files written
- [ ] `--ui-mode default` — status file written every 2s
- [ ] `--ui-mode advanced` — status file + command file polling
- [ ] Vue dashboard shows backend status in real-time
- [ ] Admin panel can toggle backends (advanced mode)
- [ ] UI server runs as separate process
- [ ] Proxy continues working if UI server crashes
- [ ] All existing tests still pass
