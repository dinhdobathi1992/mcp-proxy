from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from fastmcp.server import create_proxy

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
        ui_mode: str = "off",
        ui_status_path: str | Path | None = None,
        ui_command_path: str | Path | None = None,
        ui_update_interval: float = 5.0,
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

        self._ui_mode = ui_mode
        self._ui_status_path = ui_status_path
        self._ui_command_path = ui_command_path
        self._ui_update_interval = ui_update_interval
        self._ui_writer: Any = None
        self._ui_reader: Any = None
        self._ui_thread: threading.Thread | None = None
        self._ui_command_thread: threading.Thread | None = None

    def start(self) -> None:
        self._build_proxy()
        self._start_health_checker()
        if self._watch:
            self._start_config_watcher()
        if self._ui_mode != "off":
            self._start_ui_writer()
        if self._ui_mode == "advanced":
            self._start_ui_reader()

    def stop(self) -> None:
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
            self._watcher_thread = None
        if self._ui_thread:
            self._ui_thread.join(timeout=5.0)
            self._ui_thread = None
        if self._ui_command_thread:
            self._ui_command_thread.join(timeout=5.0)
            self._ui_command_thread = None
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

    def get_health_checker(self) -> HealthChecker | None:
        with self._lock:
            return self._health_checker

    def get_ui_status_path(self) -> Path | None:
        return Path(self._ui_status_path) if self._ui_status_path else None

    def get_ui_command_path(self) -> Path | None:
        return Path(self._ui_command_path) if self._ui_command_path else None

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

            self._proxy = create_proxy(new_config.data, name=self._name)
            self._register_management_tools(self._proxy)
            self._config = new_config

        self._start_health_checker()

    def _build_proxy(self) -> None:
        config = load_config(self._config_path, strict_startup=self._strict_startup)
        proxy = create_proxy(config.data, name=self._name)
        self._register_management_tools(proxy)

        with self._lock:
            self._proxy = proxy
            self._config = config

        backend_names = ", ".join(b.name for b in config.backends)
        LOGGER.info("Proxy started with %d backend(s): %s", len(config.backends), backend_names)

    def _register_management_tools(self, proxy: Any) -> None:
        """Register proxy_* management tools on the FastMCP proxy."""
        from .management import ManagementTools

        tools = ManagementTools(self)

        @proxy.tool()
        async def proxy_list_backends() -> str:
            """List all backends with their health status."""
            return json.dumps(tools.list_backends(), indent=2)

        @proxy.tool()
        async def proxy_add_backend(
            name: str,
            command: str = "",
            url: str = "",
            args: list[str] | None = None,
            env: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
            persist: bool = False,
        ) -> str:
            """Add a new backend at runtime."""
            return json.dumps(tools.add_backend(
                name=name,
                command=command or None,
                url=url or None,
                args=args,
                env=env,
                headers=headers,
                persist=persist,
            ), indent=2)

        @proxy.tool()
        async def proxy_remove_backend(name: str, persist: bool = False) -> str:
            """Remove a backend at runtime."""
            return json.dumps(tools.remove_backend(name, persist), indent=2)

        @proxy.tool()
        async def proxy_enable_backend(name: str, persist: bool = False) -> str:
            """Enable a disabled backend."""
            return json.dumps(tools.enable_backend(name, persist), indent=2)

        @proxy.tool()
        async def proxy_disable_backend(name: str, persist: bool = False) -> str:
            """Disable an enabled backend."""
            return json.dumps(tools.disable_backend(name, persist), indent=2)

        @proxy.tool()
        async def proxy_reload_config() -> str:
            """Force config reload from disk."""
            return json.dumps(tools.reload_config(), indent=2)

        @proxy.tool()
        async def proxy_health_status() -> str:
            """Get health status of all backends."""
            return json.dumps(tools.health_status(), indent=2)

        @proxy.tool()
        async def proxy_metrics() -> str:
            """Get proxy request metrics."""
            return json.dumps(tools.metrics(), indent=2)

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
        if config:
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
                    "errors": metrics.get("errors_per_backend", {}).get(b.name, 0),
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
                "backends": len(backends),
                "healthy": sum(1 for b in backends if b["health"] == "healthy"),
                "unhealthy": sum(1 for b in backends if b["health"] == "unhealthy"),
            },
        })

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
                    self._config_path = manager._config_path
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
