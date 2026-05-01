# mcp-proxy Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform mcp-proxy from a thin config shell into a full-featured centralized MCP proxy with hot-reload, dynamic registration, health checks, auth, metrics, and graceful shutdown.

**Architecture:** Layered enhancement — keep FastMCP `create_proxy()` for protocol handling, add management layers around it. New modules: `lifecycle.py`, `health.py`, `management.py`, `auth.py`, `metrics.py`.

**Tech Stack:** Python 3.10+, FastMCP 3.x, watchdog, pytest

---

## File Structure

```
src/mcp_proxy/
├── __init__.py              (no change)
├── cli.py                   (modify: new flags, signal handling)
├── config.py                (modify: add cwd to BackendConfig)
├── logging.py               (modify: structured JSON format)
├── server.py                (modify: use ProxyLifecycleManager)
├── validate.py              (modify: cwd validation)
├── lifecycle.py             (NEW: ProxyLifecycleManager)
├── health.py                (NEW: HealthChecker)
├── management.py            (NEW: MCP management tools)
├── auth.py                  (NEW: API key auth + rate limiting)
├── metrics.py               (NEW: in-memory metrics)
└── retry.py                 (NEW: retry policy with exponential backoff)

tests/
├── conftest.py              (modify: add shared fixtures)
├── test_config.py           (modify: add cwd tests)
├── test_validate.py         (modify: add cwd validation tests)
├── test_logging.py          (NEW: structured logging tests)
├── test_metrics.py          (NEW: metrics tests)
├── test_health.py           (NEW: health checker tests)
├── test_lifecycle.py        (NEW: lifecycle manager tests)
├── test_management.py       (NEW: management tools tests)
├── test_auth.py             (NEW: auth + rate limiting tests)
├── test_retry.py            (NEW: retry policy tests)
├── test_proxy_smoke.py      (no change)
├── test_failures.py         (no change)
└── test_real_backend.py     (no change)
```

---

## Task 1: Gap Fixes — README, cwd Validation, Resource Tests

**Files:**
- Modify: `README.md`
- Modify: `src/mcp_proxy/validate.py`
- Modify: `src/mcp_proxy/config.py`
- Modify: `tests/test_config.py`

### Step 1: Fix stale README

Remove reference to deleted `REPO_PLAN.md` and update feature list.

```markdown
# mcp-proxy

Thin FastMCP-based proxy that exposes multiple downstream MCP servers as one front MCP server.

Python 3.10+ is the intended runtime baseline.

## Goals

- One MCP server for the host to configure
- Many downstream MCP servers behind it
- `stdio` first for Claude Code, Codex, Cursor, and OpenCode
- Optional `http` front transport for remote deployments

## Quickstart

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
```

### Step 2: Add cwd validation to validate.py

Add `cwd` field validation in `normalize_backend_config`:

```python
# In normalize_backend_config(), after env/headers validation:
if "cwd" in normalized:
    cwd = normalized["cwd"]
    if not isinstance(cwd, str) or not cwd.strip():
        raise ConfigError(
            f"Backend '{backend_name}' field 'cwd' must be a non-empty string."
        )
    cwd_path = Path(cwd).expanduser()
    if not cwd_path.is_absolute():
        cwd_path = (source_path.parent / cwd_path).resolve() if source_path else cwd_path.resolve()
    if not cwd_path.is_dir():
        raise ConfigError(
            f"Backend '{backend_name}' field 'cwd' must be an existing directory: {cwd_path}"
        )
    normalized["cwd"] = str(cwd_path)
```

### Step 3: Add cwd to BackendConfig dataclass

```python
@dataclass(frozen=True, slots=True)
class BackendConfig:
    """Normalized downstream backend definition."""

    name: str
    transport: str
    enabled: bool
    raw: dict[str, Any]
    cwd: str | None = None
```

Update `load_config` to populate `cwd`:

```python
backends = tuple(
    BackendConfig(
        name=name,
        transport=backend["transport"],
        enabled=True,
        raw=backend,
        cwd=backend.get("cwd"),
    )
    for name, backend in normalized["mcpServers"].items()
)
```

### Step 4: Write cwd validation tests

```python
# In tests/test_config.py, add:

class TestCwdValidation:
    def test_valid_cwd_accepted(self, make_config_file, tmp_path):
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        config = make_config_file({
            "mcpServers": {
                "test": {
                    "command": "echo",
                    "cwd": str(workdir),
                }
            }
        })
        from mcp_proxy.config import load_config
        result = load_config(config, strict_startup=False)
        assert result.backends[0].cwd == str(workdir)

    def test_invalid_cwd_rejected(self, make_config_file, tmp_path):
        config = make_config_file({
            "mcpServers": {
                "test": {
                    "command": "echo",
                    "cwd": "/nonexistent/path",
                }
            }
        })
        from mcp_proxy.config import load_config
        from mcp_proxy.validate import ConfigError
        with pytest.raises(ConfigError, match="cwd.*existing directory"):
            load_config(config, strict_startup=False)

    def test_cwd_relative_path_resolved(self, make_config_file, tmp_path):
        workdir = tmp_path / "subdir"
        workdir.mkdir()
        config = make_config_file({
            "mcpServers": {
                "test": {
                    "command": "echo",
                    "cwd": "subdir",
                }
            }
        })
        from mcp_proxy.config import load_config
        result = load_config(config, strict_startup=False)
        assert Path(result.backends[0].cwd).is_absolute()
```

### Step 5: Run tests and verify

```bash
pytest tests/test_config.py -v
```

### Step 6: Commit

```bash
git add README.md src/mcp_proxy/validate.py src/mcp_proxy/config.py tests/test_config.py
git commit -m "fix: update README, add cwd validation and tests"
```

---

## Task 2: Structured Logging

**Files:**
- Modify: `src/mcp_proxy/logging.py`
- Create: `tests/test_logging.py`

### Step 1: Write structured logging tests

```python
# tests/test_logging.py
from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from mcp_proxy.logging import configure_logging, get_logger


class TestStructuredLogging:
    def test_text_format_default(self, capsys):
        configure_logging("INFO", log_format="text")
        logger = get_logger("test")
        logger.info("hello world")
        # Text format should produce plain log lines
        captured = capsys.readouterr()
        assert "hello world" in captured.err

    def test_json_format_produces_valid_json(self, capsys):
        configure_logging("INFO", log_format="json")
        logger = get_logger("test")
        logger.info("test message")
        captured = capsys.readouterr()
        lines = [l for l in captured.err.strip().split("\n") if l.strip()]
        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["level"] == "INFO"
        assert data["logger"] == "mcp_proxy.test"
        assert data["message"] == "test message"
        assert "timestamp" in data

    def test_json_format_includes_extra_fields(self, capsys):
        configure_logging("INFO", log_format="json")
        logger = get_logger("test")
        logger.info("with extra", extra={"backend": "echo", "duration_ms": 42})
        captured = capsys.readouterr()
        lines = [l for l in captured.err.strip().split("\n") if l.strip()]
        data = json.loads(lines[-1])
        assert data["backend"] == "echo"
        assert data["duration_ms"] == 42

    def test_log_level_filtering(self, capsys):
        configure_logging("WARNING", log_format="text")
        logger = get_logger("test")
        logger.info("should not appear")
        logger.warning("should appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.err
        assert "should appear" in captured.err
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_logging.py -v
```

Expected: FAIL (configure_logging doesn't accept log_format yet)

### Step 3: Implement structured logging

```python
# src/mcp_proxy/logging.py
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields
        for key in ("backend", "duration_ms", "request_id"):
            val = getattr(record, key, None)
            if val is not None:
                data[key] = val
        if record.exc_info and record.exc_info[1]:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def configure_logging(level: str = "INFO", log_format: str = "text") -> None:
    """Set up logging to stderr only.

    Args:
        level: Log level string.
        log_format: 'text' for plain logs, 'json' for structured JSON.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )

    root = logging.getLogger("mcp_proxy")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under mcp_proxy."""
    return logging.getLogger(f"mcp_proxy.{name}")
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_logging.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/logging.py tests/test_logging.py
git commit -m "feat: add structured JSON logging format"
```

---

## Task 3: In-Memory Metrics

**Files:**
- Create: `src/mcp_proxy/metrics.py`
- Create: `tests/test_metrics.py`

### Step 1: Write metrics tests

```python
# tests/test_metrics.py
from __future__ import annotations

import pytest

from mcp_proxy.metrics import Metrics


class TestMetrics:
    def test_record_request_increments_total(self):
        m = Metrics()
        m.record_request("echo", 10.0, True)
        m.record_request("echo", 20.0, True)
        metrics = m.get_metrics()
        assert metrics["requests_total"] == 2

    def test_record_request_per_backend(self):
        m = Metrics()
        m.record_request("echo", 10.0, True)
        m.record_request("math", 15.0, True)
        m.record_request("echo", 12.0, True)
        metrics = m.get_metrics()
        assert metrics["requests_per_backend"]["echo"] == 2
        assert metrics["requests_per_backend"]["math"] == 1

    def test_error_counter(self):
        m = Metrics()
        m.record_request("echo", 10.0, True)
        m.record_request("echo", 10.0, False)
        m.record_request("math", 10.0, False)
        metrics = m.get_metrics()
        assert metrics["errors_total"] == 2

    def test_latency_percentiles(self):
        m = Metrics()
        for i in range(100):
            m.record_request("echo", float(i), True)
        metrics = m.get_metrics()
        latency = metrics["backend_latency_ms"]["echo"]
        assert "p50" in latency
        assert "p95" in latency
        assert "p99" in latency
        assert 45 <= latency["p50"] <= 55
        assert 90 <= latency["p95"] <= 99

    def test_empty_metrics(self):
        m = Metrics()
        metrics = m.get_metrics()
        assert metrics["requests_total"] == 0
        assert metrics["errors_total"] == 0
        assert metrics["requests_per_backend"] == {}
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_metrics.py -v
```

### Step 3: Implement metrics

```python
# src/mcp_proxy/metrics.py
from __future__ import annotations

import statistics
import threading
from collections import defaultdict
from typing import Any


class Metrics:
    """Thread-safe in-memory metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._per_backend: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)

    def record_request(self, backend_name: str, duration_ms: float, success: bool) -> None:
        with self._lock:
            self._requests_total += 1
            self._per_backend[backend_name] += 1
            self._latencies[backend_name].append(duration_ms)
            if not success:
                self._errors_total += 1

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            latency_percentiles: dict[str, dict[str, float]] = {}
            for name, values in self._latencies.items():
                if values:
                    latency_percentiles[name] = {
                        "p50": statistics.median(values),
                        "p95": self._percentile(values, 95),
                        "p99": self._percentile(values, 99),
                    }
                else:
                    latency_percentiles[name] = {"p50": 0.0, "p95": 0.0, "p99": 0.0}

            return {
                "requests_total": self._requests_total,
                "requests_per_backend": dict(self._per_backend),
                "errors_total": self._errors_total,
                "backend_latency_ms": latency_percentiles,
            }

    @staticmethod
    def _percentile(values: list[float], pct: int) -> float:
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_vals):
            return sorted_vals[-1]
        return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_metrics.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/metrics.py tests/test_metrics.py
git commit -m "feat: add in-memory metrics collector"
```

---

## Task 4: Health Checker

**Files:**
- Create: `src/mcp_proxy/health.py`
- Create: `tests/test_health.py`

### Step 1: Write health checker tests

```python
# tests/test_health.py
from __future__ import annotations

import pytest

from mcp_proxy.health import HealthChecker, HealthStatus


class TestHealthStatus:
    def test_initial_state_is_unknown(self):
        checker = HealthChecker(backends=[], interval=1.0)
        assert checker.get_status("any") == HealthStatus.UNKNOWN

    def test_get_all_status_empty(self):
        checker = HealthChecker(backends=[], interval=1.0)
        assert checker.get_all_status() == {}


class TestHealthCheckerLifecycle:
    def test_start_and_stop(self):
        checker = HealthChecker(backends=[], interval=1.0)
        checker.start()
        assert checker._task is not None
        checker.stop()
        assert checker._task is None

    def test_stop_without_start_is_noop(self):
        checker = HealthChecker(backends=[], interval=1.0)
        checker.stop()  # Should not raise
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_health.py -v
```

### Step 3: Implement health checker

```python
# src/mcp_proxy/health.py
from __future__ import annotations

import asyncio
import enum
import threading
from typing import Any, Callable


class HealthStatus(enum.Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    """Periodic health checker for MCP backends."""

    def __init__(
        self,
        backends: list[dict[str, Any]],
        interval: float = 30.0,
        on_status_change: Callable[[str, HealthStatus], None] | None = None,
    ) -> None:
        self._backends = backends
        self._interval = interval
        self._on_status_change = on_status_change
        self._status: dict[str, HealthStatus] = {}
        self._task: threading.Thread | None = None
        self._stop_event = threading.Event()

    def get_status(self, backend_name: str) -> HealthStatus:
        return self._status.get(backend_name, HealthStatus.UNKNOWN)

    def get_all_status(self) -> dict[str, HealthStatus]:
        return dict(self._status)

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = threading.Thread(target=self._run, daemon=True)
        self._task.start()

    def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        self._task.join(timeout=5.0)
        self._task = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check_all()
            self._stop_event.wait(self._interval)

    def _check_all(self) -> None:
        for backend in self._backends:
            name = backend.get("name", "unknown")
            old_status = self._status.get(name, HealthStatus.UNKNOWN)
            new_status = self._ping_backend(backend)
            self._status[name] = new_status
            if old_status != new_status and self._on_status_change:
                self._on_status_change(name, new_status)

    def _ping_backend(self, backend: dict[str, Any]) -> HealthStatus:
        """Ping a single backend. Returns HEALTHY or UNHEALTHY."""
        try:
            transport = backend.get("transport", "stdio")
            if transport == "stdio":
                return self._ping_stdio(backend)
            else:
                return self._ping_http(backend)
        except Exception:
            return HealthStatus.UNHEALTHY

    def _ping_stdio(self, backend: dict[str, Any]) -> HealthStatus:
        """Check stdio backend by verifying the subprocess is alive."""
        proc = backend.get("_process")
        if proc is None:
            return HealthStatus.UNKNOWN
        if proc.poll() is not None:
            return HealthStatus.UNHEALTHY
        return HealthStatus.HEALTHY

    def _ping_http(self, backend: dict[str, Any]) -> HealthStatus:
        """Check HTTP backend with a simple request."""
        import urllib.request
        import urllib.error

        url = backend.get("url", "")
        if not url:
            return HealthStatus.UNKNOWN
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5.0):
                return HealthStatus.HEALTHY
        except (urllib.error.URLError, OSError, TimeoutError):
            return HealthStatus.UNHEALTHY
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_health.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/health.py tests/test_health.py
git commit -m "feat: add health checker for MCP backends"
```

---

## Task 5: API Key Authentication & Rate Limiting

**Files:**
- Create: `src/mcp_proxy/auth.py`
- Create: `tests/test_auth.py`

### Step 1: Write auth tests

```python
# tests/test_auth.py
from __future__ import annotations

import time

import pytest

from mcp_proxy.auth import APIKeyAuth, RateLimiter


class TestAPIKeyAuth:
    def test_no_key_configured_allows_all(self):
        auth = APIKeyAuth(api_key=None)
        assert auth.validate("Bearer anything") is True
        assert auth.validate("") is True

    def test_valid_key_accepted(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("Bearer secret123") is True

    def test_invalid_key_rejected(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("Bearer wrong") is False

    def test_missing_header_rejected(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("") is False
        assert auth.validate(None) is False

    def test_malformed_header_rejected(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("Basic secret123") is False


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.allow("127.0.0.1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.allow("127.0.0.1") is True
        assert limiter.allow("127.0.0.1") is False

    def test_different_ips_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.2") is True
        assert limiter.allow("10.0.0.2") is True
        assert limiter.allow("10.0.0.1") is False
        assert limiter.allow("10.0.0.2") is False

    def test_window_expiry_resets(self):
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        assert limiter.allow("127.0.0.1") is True
        assert limiter.allow("127.0.0.1") is True
        assert limiter.allow("127.0.0.1") is False
        time.sleep(0.15)
        assert limiter.allow("127.0.0.1") is True
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_auth.py -v
```

### Step 3: Implement auth and rate limiter

```python
# src/mcp_proxy/auth.py
from __future__ import annotations

import threading
import time
from collections import defaultdict


class APIKeyAuth:
    """Simple bearer token authentication."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def validate(self, auth_header: str | None) -> bool:
        """Validate an Authorization header value.

        Returns True if valid (or no key configured), False otherwise.
        """
        if self._api_key is None:
            return True
        if not auth_header:
            return False
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer":
            return False
        return parts[1] == self._api_key


class RateLimiter:
    """Sliding window rate limiter per client IP."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, list[float]] = defaultdict(list)

    def allow(self, client_ip: str) -> bool:
        """Check if a request from client_ip is allowed."""
        now = time.monotonic()
        with self._lock:
            timestamps = self._requests[client_ip]
            # Remove expired entries
            cutoff = now - self._window
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            if len(timestamps) >= self._max:
                return False
            timestamps.append(now)
            return True
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_auth.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/auth.py tests/test_auth.py
git commit -m "feat: add API key auth and rate limiter"
```

---

## Task 6: Graceful Shutdown

**Files:**
- Modify: `src/mcp_proxy/cli.py`
- Modify: `src/mcp_proxy/server.py`
- Modify: `tests/test_failures.py`

### Step 1: Write graceful shutdown test

```python
# In tests/test_failures.py, add:

class TestGracefulShutdown:
    def test_sigint_returns_130(self, stdio_config, monkeypatch):
        """Verify SIGINT is caught and returns exit code 130."""
        import signal
        from mcp_proxy.cli import main

        # Simulate SIGINT after a short delay
        def raise_keyboard_interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr("mcp_proxy.server.run_proxy", raise_keyboard_interrupt)
        result = main(["--config", str(stdio_config)])
        assert result == 130
```

### Step 2: Run test to verify it passes (already handled)

```bash
pytest tests/test_failures.py::TestGracefulShutdown -v
```

### Step 3: Add signal handling to cli.py

```python
# In cli.py, add signal handling:
import signal

def _setup_signal_handlers(lifecycle_manager):
    """Set up graceful shutdown on SIGINT/SIGTERM."""
    def handler(signum, frame):
        LOGGER.info("Received signal %s, shutting down gracefully...", signum)
        lifecycle_manager.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
```

### Step 4: Commit

```bash
git add src/mcp_proxy/cli.py tests/test_failures.py
git commit -m "feat: add graceful shutdown signal handling"
```

---

## Task 7: Config Hot-Reload (Lifecycle Manager)

**Files:**
- Create: `src/mcp_proxy/lifecycle.py`
- Create: `tests/test_lifecycle.py`
- Modify: `src/mcp_proxy/server.py`
- Modify: `pyproject.toml`

### Step 1: Add watchdog dependency

```toml
# In pyproject.toml dependencies:
dependencies = [
  "fastmcp>=3.2.4,<4",
  "watchdog>=4.0.0",
]
```

### Step 2: Write lifecycle manager tests

```python
# tests/test_lifecycle.py
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from mcp_proxy.lifecycle import ProxyLifecycleManager


class TestProxyLifecycleManager:
    def test_start_builds_proxy(self, stdio_config: Path):
        mgr = ProxyLifecycleManager(stdio_config, name="test")
        mgr.start()
        assert mgr.get_proxy() is not None
        assert mgr.get_config() is not None
        mgr.stop()

    def test_rebuild_proxy_on_config_change(self, stdio_config: Path, make_config_file, tmp_path):
        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        original_config = mgr.get_config()

        # Modify config
        new_data = json.loads(stdio_config.read_text())
        new_data["mcpServers"]["new_backend"] = {
            "command": "echo",
            "args": ["hello"],
        }
        stdio_config.write_text(json.dumps(new_data))

        mgr.rebuild_proxy()
        new_config = mgr.get_config()
        assert len(new_config.backends) == len(original_config.backends) + 1
        mgr.stop()

    def test_rebuild_preserves_on_invalid_config(self, stdio_config: Path):
        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        original_proxy = mgr.get_proxy()

        # Write invalid config
        stdio_config.write_text("not json")

        mgr.rebuild_proxy()
        # Should keep original proxy
        assert mgr.get_proxy() is original_proxy
        mgr.stop()

    def test_get_proxy_thread_safe(self, stdio_config: Path):
        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        proxy1 = mgr.get_proxy()
        proxy2 = mgr.get_proxy()
        assert proxy1 is proxy2
        mgr.stop()
```

### Step 3: Run tests to verify they fail

```bash
pytest tests/test_lifecycle.py -v
```

### Step 4: Implement lifecycle manager

```python
# src/mcp_proxy/lifecycle.py
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from .config import ProxyConfig, load_config
from .health import HealthChecker
from .logging import get_logger
from .metrics import Metrics
from .validate import ConfigError

LOGGER = get_logger("lifecycle")


class ProxyLifecycleManager:
    """Manages the FastMCP proxy lifecycle: config, health, hot-reload."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        name: str = "mcp-proxy",
        strict_startup: bool = True,
        watch: bool = False,
        health_interval: float = 30.0,
    ) -> None:
        self._config_path = Path(config_path)
        self._name = name
        self._strict_startup = strict_startup
        self._watch = watch
        self._health_interval = health_interval

        self._lock = threading.Lock()
        self._proxy: Any = None
        self._config: ProxyConfig | None = None
        self._health_checker: HealthChecker | None = None
        self._watcher_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._metrics = Metrics()

    def start(self) -> None:
        """Build initial proxy, start health checker and config watcher."""
        self._build_proxy()
        self._start_health_checker()
        if self._watch:
            self._start_config_watcher()

    def stop(self) -> None:
        """Graceful shutdown: stop watcher, health checker."""
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
            self._watcher_thread = None
        if self._health_checker:
            self._health_checker.stop()
            self._health_checker = None

    def get_proxy(self) -> Any:
        """Return current proxy instance (thread-safe)."""
        with self._lock:
            return self._proxy

    def get_config(self) -> ProxyConfig | None:
        """Return current proxy config."""
        with self._lock:
            return self._config

    def get_metrics(self) -> Metrics:
        """Return the metrics collector."""
        return self._metrics

    def rebuild_proxy(self) -> None:
        """Re-read config and rebuild proxy if changed."""
        try:
            new_config = load_config(
                self._config_path, strict_startup=self._strict_startup
            )
        except ConfigError as exc:
            LOGGER.warning("Config reload failed, keeping current: %s", exc)
            return

        with self._lock:
            old_backend_names = {b.name for b in self._config.backends} if self._config else set()
            new_backend_names = {b.name for b in new_config.backends}
            added = new_backend_names - old_backend_names
            removed = old_backend_names - new_backend_names

            if added:
                LOGGER.info("Backends added: %s", ", ".join(added))
            if removed:
                LOGGER.info("Backends removed: %s", ", ".join(removed))

            from fastmcp.server import create_proxy

            self._proxy = create_proxy(new_config.data, name=self._name)
            self._config = new_config

        self._start_health_checker()

    def _build_proxy(self) -> None:
        """Initial proxy build."""
        from fastmcp.server import create_proxy

        config = load_config(self._config_path, strict_startup=self._strict_startup)
        proxy = create_proxy(config.data, name=self._name)

        with self._lock:
            self._proxy = proxy
            self._config = config

        backend_names = ", ".join(b.name for b in config.backends)
        LOGGER.info("Proxy started with %d backend(s): %s", len(config.backends), backend_names)

    def _start_health_checker(self) -> None:
        """Start or restart the health checker."""
        if self._health_checker:
            self._health_checker.stop()

        with self._lock:
            if not self._config:
                return
            backends = [
                {"name": b.name, "transport": b.transport, **b.raw}
                for b in self._config.backends
            ]

        self._health_checker = HealthChecker(
            backends=backends,
            interval=self._health_interval,
            on_status_change=self._on_health_change,
        )
        self._health_checker.start()

    def _on_health_change(self, backend_name: str, status) -> None:
        LOGGER.info("Backend '%s' health changed to %s", backend_name, status.value)

    def _start_config_watcher(self) -> None:
        """Start watching config file for changes."""
        self._watcher_thread = threading.Thread(
            target=self._watch_config_file, daemon=True
        )
        self._watcher_thread.start()

    def _watch_config_file(self) -> None:
        """Poll config file for changes (simple fallback)."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent

            class ConfigHandler(FileSystemEventHandler):
                def __init__(self, manager: ProxyLifecycleManager):
                    self._manager = manager
                    self._last_reload = 0.0

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    if Path(event.src_path).resolve() != self._config_path.resolve():
                        return
                    now = time.monotonic()
                    if now - self._last_reload < 0.5:  # debounce
                        return
                    self._last_reload = now
                    LOGGER.info("Config file changed, reloading...")
                    self._manager.rebuild_proxy()

            handler = ConfigHandler(self)
            observer = Observer()
            observer.schedule(handler, str(self._config_path.parent), recursive=False)
            observer.start()

            self._stop_event.wait()
            observer.stop()
            observer.join()

        except ImportError:
            LOGGER.info("watchdog not available, using polling for config watching")
            self._poll_config_file()

    def _poll_config_file(self) -> None:
        """Fallback: poll config file for changes."""
        last_mtime = self._config_path.stat().st_mtime
        while not self._stop_event.is_set():
            self._stop_event.wait(5.0)
            if self._stop_event.is_set():
                break
            try:
                current_mtime = self._config_path.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    LOGGER.info("Config file changed (poll), reloading...")
                    self.rebuild_proxy()
            except OSError:
                pass
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/test_lifecycle.py -v
```

### Step 6: Update server.py to use lifecycle manager

```python
# src/mcp_proxy/server.py — refactor to delegate to lifecycle manager
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ProxyConfig
from .lifecycle import ProxyLifecycleManager
from .logging import get_logger
from .validate import validate_front_transport

LOGGER = get_logger("server")


def build_proxy(
    config_path: str | Path,
    *,
    name: str = "mcp-proxy",
    strict_startup: bool = True,
) -> tuple[Any, ProxyConfig]:
    """Load config and build the FastMCP proxy instance."""
    mgr = ProxyLifecycleManager(
        config_path, name=name, strict_startup=strict_startup
    )
    mgr.start()
    return mgr.get_proxy(), mgr.get_config()


def run_proxy(
    config_path: str | Path,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    name: str = "mcp-proxy",
    strict_startup: bool = True,
    watch: bool = False,
    health_interval: float = 30.0,
) -> int:
    """Run the proxy using the selected front transport."""

    front_transport = validate_front_transport(transport)
    mgr = ProxyLifecycleManager(
        config_path,
        name=name,
        strict_startup=strict_startup,
        watch=watch,
        health_interval=health_interval,
    )
    mgr.start()

    proxy = mgr.get_proxy()
    config = mgr.get_config()
    backend_names = ", ".join(backend.name for backend in config.backends)

    if front_transport == "stdio":
        LOGGER.info(
            "Starting MCP proxy via stdio with %d backend(s): %s",
            len(config.backends),
            backend_names,
        )
        proxy.run(transport="stdio")
        return 0

    LOGGER.info(
        "Starting MCP proxy via http on %s:%s with %d backend(s): %s",
        host,
        port,
        len(config.backends),
        backend_names,
    )
    proxy.run(transport="http", host=host, port=port)
    return 0
```

### Step 7: Commit

```bash
git add src/mcp_proxy/lifecycle.py tests/test_lifecycle.py src/mcp_proxy/server.py pyproject.toml
git commit -m "feat: add lifecycle manager with config hot-reload"
```

---

## Task 7b: Retry & Reconnect

**Files:**
- Create: `src/mcp_proxy/retry.py`
- Create: `tests/test_retry.py`
- Modify: `src/mcp_proxy/lifecycle.py`

### Step 1: Write retry tests

```python
# tests/test_retry.py
from __future__ import annotations

import pytest

from mcp_proxy.retry import RetryPolicy, with_retry


class TestRetryPolicy:
    def test_defaults(self):
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.initial_backoff == 0.1

    def test_custom_values(self):
        policy = RetryPolicy(max_retries=5, initial_backoff=0.5)
        assert policy.max_retries == 5
        assert policy.initial_backoff == 0.5


class TestWithRetry:
    def test_success_no_retry(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = with_retry(fn, RetryPolicy(max_retries=3))
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        result = with_retry(fn, RetryPolicy(max_retries=3, initial_backoff=0.01))
        assert result == "ok"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        def fn():
            raise ConnectionError("always fail")

        with pytest.raises(ConnectionError):
            with_retry(fn, RetryPolicy(max_retries=2, initial_backoff=0.01))

    def test_no_retry_on_non_retryable_error(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            with_retry(fn, RetryPolicy(max_retries=3, initial_backoff=0.01))
        assert call_count == 1

    def test_exponential_backoff(self):
        import time

        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        start = time.monotonic()
        with_retry(fn, RetryPolicy(max_retries=3, initial_backoff=0.05))
        elapsed = time.monotonic() - start
        # Should have waited at least 0.05 + 0.1 = 0.15s
        assert elapsed >= 0.1
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_retry.py -v
```

### Step 3: Implement retry policy

```python
# src/mcp_proxy/retry.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

T = TypeVar("T")

RETRYABLE_ERRORS = (ConnectionError, OSError, TimeoutError)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_backoff: float = 0.1
    backoff_multiplier: float = 2.0


def with_retry(
    fn: Callable[..., T],
    policy: RetryPolicy | None = None,
) -> T:
    """Execute fn with retry on transient errors.

    Args:
        fn: Callable to execute.
        policy: Retry configuration.

    Returns:
        Result of fn().

    Raises:
        The last exception if all retries are exhausted, or non-retryable errors immediately.
    """
    if policy is None:
        policy = RetryPolicy()

    last_error: Exception | None = None
    backoff = policy.initial_backoff

    for attempt in range(policy.max_retries + 1):
        try:
            return fn()
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < policy.max_retries:
                time.sleep(backoff)
                backoff *= policy.backoff_multiplier
            else:
                raise
        except Exception:
            raise

    raise last_error  # type: ignore[misc]
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_retry.py -v
```

### Step 5: Integrate retry into lifecycle manager

Add retry wrapping for backend requests in `lifecycle.py`:

```python
# In lifecycle.py, add import:
from .retry import RetryPolicy, with_retry

# In ProxyLifecycleManager.__init__:
self._retry_policy = RetryPolicy(max_retries=max_retries, initial_backoff=retry_backoff)

# Add max_retries and retry_backoff parameters to __init__
```

### Step 6: Commit

```bash
git add src/mcp_proxy/retry.py tests/test_retry.py src/mcp_proxy/lifecycle.py
git commit -m "feat: add retry policy with exponential backoff"
```

---

## Task 8: Management Tools

**Files:**
- Create: `src/mcp_proxy/management.py`
- Create: `tests/test_management.py`

### Step 1: Write management tools tests

```python
# tests/test_management.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_proxy.management import ManagementTools


class TestManagementTools:
    def test_list_backends(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test")
        mgr.start()
        tools = ManagementTools(mgr)
        result = tools.list_backends()
        assert len(result) == 1
        assert result[0]["name"] == "echo"
        assert result[0]["enabled"] is True
        mgr.stop()

    def test_add_backend_runtime(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.add_backend(
            name="new",
            command="echo",
            args=["hello"],
        )
        assert result["success"] is True
        assert "new" in [b.name for b in mgr.get_config().backends]
        mgr.stop()

    def test_remove_backend_runtime(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.remove_backend("echo")
        assert result["success"] is True
        # After removal, no backends left — config should still be valid
        # (lifecycle manager handles this)
        mgr.stop()

    def test_disable_backend(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.disable_backend("echo")
        assert result["success"] is True
        mgr.stop()

    def test_enable_backend(self, stdio_config: Path, make_config_file, python_exe, backend_stdio_path):
        config = make_config_file({
            "mcpServers": {
                "echo": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                    "enabled": False,
                }
            }
        })
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(config, name="test", strict_startup=False, watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.enable_backend("echo")
        assert result["success"] is True
        mgr.stop()

    def test_health_status(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.health_status()
        assert "backends" in result
        mgr.stop()

    def test_metrics(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.metrics()
        assert "requests_total" in result
        mgr.stop()
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_management.py -v
```

### Step 3: Implement management tools

```python
# src/mcp_proxy/management.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_config
from .health import HealthStatus
from .lifecycle import ProxyLifecycleManager
from .logging import get_logger
from .validate import ConfigError

LOGGER = get_logger("management")


class ManagementTools:
    """MCP tools for runtime proxy management."""

    def __init__(self, lifecycle: ProxyLifecycleManager) -> None:
        self._lifecycle = lifecycle

    def list_backends(self) -> list[dict[str, Any]]:
        """List all backends with status."""
        config = self._lifecycle.get_config()
        if not config:
            return []

        health = self._lifecycle._health_checker
        result = []
        for backend in config.backends:
            status = HealthStatus.UNKNOWN
            if health:
                status = health.get_status(backend.name)
            result.append({
                "name": backend.name,
                "transport": backend.transport,
                "enabled": backend.enabled,
                "health": status.value,
            })
        return result

    def add_backend(
        self,
        name: str,
        *,
        command: str | None = None,
        url: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        """Add a backend to the runtime config."""
        config = self._lifecycle.get_config()
        if not config:
            return {"success": False, "error": "No config loaded"}

        # Check if backend already exists
        existing_names = {b.name for b in config.backends}
        if name in existing_names:
            return {"success": False, "error": f"Backend '{name}' already exists"}

        # Build new backend entry
        entry: dict[str, Any] = {}
        if command:
            entry["command"] = command
            if args:
                entry["args"] = args
            if env:
                entry["env"] = env
        elif url:
            entry["url"] = url
            if headers:
                entry["headers"] = headers
        else:
            return {"success": False, "error": "Must provide 'command' or 'url'"}

        # Update config data
        new_data = dict(config.data)
        new_servers = dict(new_data.get("mcpServers", {}))
        new_servers[name] = entry
        new_data["mcpServers"] = new_servers

        # Write to temp file and rebuild
        if persist:
            self._persist_config(config.path, new_data)

        # Trigger rebuild
        self._lifecycle.rebuild_proxy()
        return {"success": True, "message": f"Backend '{name}' added"}

    def remove_backend(self, name: str, persist: bool = False) -> dict[str, Any]:
        """Remove a backend from runtime config."""
        config = self._lifecycle.get_config()
        if not config:
            return {"success": False, "error": "No config loaded"}

        new_data = dict(config.data)
        new_servers = dict(new_data.get("mcpServers", {}))
        if name not in new_servers:
            return {"success": False, "error": f"Backend '{name}' not found"}
        del new_servers[name]

        if not new_servers:
            return {"success": False, "error": "Cannot remove last backend"}

        new_data["mcpServers"] = new_servers
        if persist:
            self._persist_config(config.path, new_data)

        self._lifecycle.rebuild_proxy()
        return {"success": True, "message": f"Backend '{name}' removed"}

    def enable_backend(self, name: str, persist: bool = False) -> dict[str, Any]:
        """Enable a disabled backend."""
        return self._set_backend_enabled(name, True, persist)

    def disable_backend(self, name: str, persist: bool = False) -> dict[str, Any]:
        """Disable an enabled backend."""
        return self._set_backend_enabled(name, False, persist)

    def reload_config(self) -> dict[str, Any]:
        """Force config reload from disk."""
        self._lifecycle.rebuild_proxy()
        config = self._lifecycle.get_config()
        return {
            "success": True,
            "backends": [b.name for b in config.backends] if config else [],
        }

    def health_status(self) -> dict[str, Any]:
        """Get health status of all backends."""
        health = self._lifecycle._health_checker
        if not health:
            return {"backends": {}}

        all_status = health.get_all_status()
        return {
            "backends": {name: status.value for name, status in all_status.items()}
        }

    def metrics(self) -> dict[str, Any]:
        """Get proxy metrics."""
        return self._lifecycle.get_metrics().get_metrics()

    def _set_backend_enabled(
        self, name: str, enabled: bool, persist: bool
    ) -> dict[str, Any]:
        config = self._lifecycle.get_config()
        if not config:
            return {"success": False, "error": "No config loaded"}

        new_data = dict(config.data)
        new_servers = dict(new_data.get("mcpServers", {}))
        if name not in new_servers:
            return {"success": False, "error": f"Backend '{name}' not found"}

        entry = dict(new_servers[name])
        entry["enabled"] = enabled
        new_servers[name] = entry
        new_data["mcpServers"] = new_servers

        if persist:
            self._persist_config(config.path, new_data)

        self._lifecycle.rebuild_proxy()
        action = "enabled" if enabled else "disabled"
        return {"success": True, "message": f"Backend '{name}' {action}"}

    def _persist_config(self, config_path: Path, data: dict[str, Any]) -> None:
        """Write config to disk."""
        try:
            config_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            LOGGER.info("Config persisted to %s", config_path)
        except OSError as exc:
            LOGGER.warning("Failed to persist config: %s", exc)
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/test_management.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/management.py tests/test_management.py
git commit -m "feat: add MCP management tools for runtime backend control"
```

---

## Task 9: CLI Updates & Integration

**Files:**
- Modify: `src/mcp_proxy/cli.py`
- Modify: `tests/test_failures.py`

### Step 1: Add new CLI flags

```python
# In cli.py build_parser(), add:
parser.add_argument(
    "--watch",
    action="store_true",
    help="Watch config file for changes and hot-reload.",
)
parser.add_argument(
    "--health-interval",
    type=float,
    default=30.0,
    help="Health check interval in seconds.",
)
parser.add_argument(
    "--auth-api-key",
    default=None,
    help="API key for HTTP front authentication.",
)
parser.add_argument(
    "--rate-limit",
    type=int,
    default=100,
    help="Requests per minute per IP (HTTP only).",
)
parser.add_argument(
    "--tls-cert",
    default=None,
    help="TLS certificate path for HTTPS.",
)
parser.add_argument(
    "--tls-key",
    default=None,
    help="TLS key path for HTTPS.",
)
parser.add_argument(
    "--log-format",
    choices=("text", "json"),
    default="text",
    help="Log format: text or json.",
)
```

### Step 2: Update main() to pass new flags

```python
# In cli.py main():
configure_logging(args.log_level, log_format=args.log_format)

# Update run_proxy call:
return run_proxy(
    args.config,
    transport=args.transport,
    host=args.host,
    port=args.port,
    name=args.name,
    strict_startup=args.strict_startup,
    watch=args.watch,
    health_interval=args.health_interval,
)
```

### Step 3: Write CLI integration test

```python
# In tests/test_failures.py, add:

class TestNewCliFlags:
    def test_watch_flag_accepted(self, stdio_config):
        from mcp_proxy.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--config", str(stdio_config), "--watch"])
        assert args.watch is True

    def test_health_interval_flag(self, stdio_config):
        from mcp_proxy.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--config", str(stdio_config), "--health-interval", "10"])
        assert args.health_interval == 10.0

    def test_log_format_json(self, stdio_config):
        from mcp_proxy.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--config", str(stdio_config), "--log-format", "json"])
        assert args.log_format == "json"
```

### Step 4: Run tests

```bash
pytest tests/test_failures.py -v
```

### Step 5: Commit

```bash
git add src/mcp_proxy/cli.py tests/test_failures.py
git commit -m "feat: add CLI flags for watch, health, auth, log-format"
```

---

## Task 10: Final Integration & README Update

**Files:**
- Modify: `README.md`
- Modify: `docs/client-compatibility.md`

### Step 1: Update README with all new features

```markdown
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

## Quickstart

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

```bash
# Validate config
mcp-proxy --config servers.json --check

# Run with hot-reload
mcp-proxy --config servers.json --watch

# Run as HTTP server with auth
mcp-proxy --config servers.json --transport http --auth-api-key mysecret

# Run with JSON logging
mcp-proxy --config servers.json --log-format json
```

## Management Tools

When running, the proxy exposes these MCP tools:

- `proxy_list_backends` — list all backends with health status
- `proxy_add_backend` — add a backend at runtime
- `proxy_remove_backend` — remove a backend
- `proxy_enable_backend` / `proxy_disable_backend` — toggle backends
- `proxy_reload_config` — force config reload
- `proxy_health_status` — get health status
- `proxy_metrics` — get request metrics

## Compatibility Notes

- Logs go to stderr (MCP stdout stays clean)
- `stdio` is the primary target for local host integration
- Example host configs live under `examples/`
- Additional host notes live in `docs/client-compatibility.md`
```

### Step 2: Run full test suite

```bash
pytest tests/ -v
```

### Step 3: Commit

```bash
git add README.md docs/client-compatibility.md
git commit -m "docs: update README with all new features"
```

---

## Task 11: TLS Support

**Files:**
- Modify: `src/mcp_proxy/server.py`
- Modify: `src/mcp_proxy/cli.py`

### Step 1: Add TLS to run_proxy

```python
# In server.py run_proxy(), update HTTP transport section:

if front_transport == "http":
    LOGGER.info(
        "Starting MCP proxy via %s on %s:%s with %d backend(s): %s",
        "https" if tls_cert else "http",
        host,
        port,
        len(config.backends),
        backend_names,
    )
    if tls_cert and tls_key:
        proxy.run(transport="http", host=host, port=port, ssl_certfile=tls_cert, ssl_keyfile=tls_key)
    else:
        proxy.run(transport="http", host=host, port=port)
    return 0
```

### Step 2: Update run_proxy signature

```python
def run_proxy(
    config_path: str | Path,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    name: str = "mcp-proxy",
    strict_startup: bool = True,
    watch: bool = False,
    health_interval: float = 30.0,
    tls_cert: str | None = None,
    tls_key: str | None = None,
) -> int:
```

### Step 3: Update cli.py to pass TLS flags

```python
# In cli.py main():
return run_proxy(
    args.config,
    transport=args.transport,
    host=args.host,
    port=args.port,
    name=args.name,
    strict_startup=args.strict_startup,
    watch=args.watch,
    health_interval=args.health_interval,
    tls_cert=args.tls_cert,
    tls_key=args.tls_key,
)
```

### Step 4: Commit

```bash
git add src/mcp_proxy/server.py src/mcp_proxy/cli.py
git commit -m "feat: add TLS support for HTTPS front transport"
```

---

## Verification Checklist

After all tasks are complete, verify:

- [ ] `pytest tests/ -v` — all tests pass
- [ ] `mcp-proxy --config servers.example.json --check` — config validation works
- [ ] `mcp-proxy --config servers.example.json --watch` — hot-reload works
- [ ] Management tools are callable from MCP host
- [ ] Health checker reports backend status
- [ ] Graceful shutdown on SIGINT/SIGTERM
- [ ] JSON logging format works
- [ ] API key auth works on HTTP transport
