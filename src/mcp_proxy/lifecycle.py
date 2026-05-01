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
from .retry import RetryPolicy
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
        max_retries: int = 3,
        retry_backoff: float = 0.1,
    ) -> None:
        self._config_path = Path(config_path)
        self._name = name
        self._strict_startup = strict_startup
        self._watch = watch
        self._health_interval = health_interval
        self._retry_policy = RetryPolicy(max_retries=max_retries, initial_backoff=retry_backoff)

        self._lock = threading.Lock()
        self._proxy: Any = None
        self._config: ProxyConfig | None = None
        self._health_checker: HealthChecker | None = None
        self._watcher_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._metrics = Metrics()

    def start(self) -> None:
        self._build_proxy()
        self._start_health_checker()
        if self._watch:
            self._start_config_watcher()

    def stop(self) -> None:
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
            self._watcher_thread = None
        if self._health_checker:
            self._health_checker.stop()
            self._health_checker = None

    def get_proxy(self) -> Any:
        with self._lock:
            return self._proxy

    def get_config(self) -> ProxyConfig | None:
        with self._lock:
            return self._config

    def get_metrics(self) -> Metrics:
        return self._metrics

    def rebuild_proxy(self) -> None:
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
        from fastmcp.server import create_proxy

        config = load_config(self._config_path, strict_startup=self._strict_startup)
        proxy = create_proxy(config.data, name=self._name)

        with self._lock:
            self._proxy = proxy
            self._config = config

        backend_names = ", ".join(b.name for b in config.backends)
        LOGGER.info("Proxy started with %d backend(s): %s", len(config.backends), backend_names)

    def _start_health_checker(self) -> None:
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
        self._watcher_thread = threading.Thread(
            target=self._watch_config_file, daemon=True
        )
        self._watcher_thread.start()

    def _watch_config_file(self) -> None:
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
                    if now - self._last_reload < 0.5:
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
