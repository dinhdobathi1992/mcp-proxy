from __future__ import annotations

import enum
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

DEFAULT_HTTP_TIMEOUT_SEC = 5.0


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
        self._status_lock = threading.Lock()
        self._task: threading.Thread | None = None
        self._stop_event = threading.Event()

    def get_status(self, backend_name: str) -> HealthStatus:
        with self._status_lock:
            return self._status.get(backend_name, HealthStatus.UNKNOWN)

    def get_all_status(self) -> dict[str, HealthStatus]:
        with self._status_lock:
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
            new_status = self._ping_backend(backend)
            with self._status_lock:
                old_status = self._status.get(name, HealthStatus.UNKNOWN)
                self._status[name] = new_status
                changed = old_status != new_status
            if changed and self._on_status_change:
                self._on_status_change(name, new_status)

    def _ping_backend(self, backend: dict[str, Any]) -> HealthStatus:
        try:
            transport = backend.get("transport", "stdio")
            if transport == "stdio":
                return self._ping_stdio(backend)
            return self._ping_http(backend)
        except Exception:
            return HealthStatus.UNHEALTHY

    def _ping_stdio(self, backend: dict[str, Any]) -> HealthStatus:
        """Check stdio backend health.

        FastMCP manages stdio subprocesses internally. We can't access the
        process object directly, so we verify the command exists on the system.
        """
        command = backend.get("command", "")
        if not command:
            return HealthStatus.UNKNOWN
        if shutil.which(command):
            return HealthStatus.HEALTHY
        path = Path(command)
        if path.is_absolute() and path.is_file():
            return HealthStatus.HEALTHY
        return HealthStatus.UNHEALTHY

    def _ping_http(self, backend: dict[str, Any]) -> HealthStatus:
        url = backend.get("url", "")
        if not url:
            return HealthStatus.UNKNOWN
        timeout = backend.get("timeout") or DEFAULT_HTTP_TIMEOUT_SEC
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout):
                return HealthStatus.HEALTHY
        except (urllib.error.URLError, OSError, TimeoutError):
            return HealthStatus.UNHEALTHY
