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
        config = self._lifecycle.get_config()
        if not config:
            return {"success": False, "error": "No config loaded"}

        existing_names = {b.name for b in config.backends}
        if name in existing_names:
            return {"success": False, "error": f"Backend '{name}' already exists"}

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

        new_data = dict(config.data)
        new_servers = dict(new_data.get("mcpServers", {}))
        new_servers[name] = entry
        new_data["mcpServers"] = new_servers

        self._write_config(config.path, new_data)
        self._lifecycle.rebuild_proxy()
        return {"success": True, "message": f"Backend '{name}' added"}

    def remove_backend(self, name: str, persist: bool = False) -> dict[str, Any]:
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
        self._write_config(config.path, new_data)
        self._lifecycle.rebuild_proxy()
        return {"success": True, "message": f"Backend '{name}' removed"}

    def enable_backend(self, name: str, persist: bool = False) -> dict[str, Any]:
        return self._set_backend_enabled(name, True, persist)

    def disable_backend(self, name: str, persist: bool = False) -> dict[str, Any]:
        return self._set_backend_enabled(name, False, persist)

    def reload_config(self) -> dict[str, Any]:
        self._lifecycle.rebuild_proxy()
        config = self._lifecycle.get_config()
        return {
            "success": True,
            "backends": [b.name for b in config.backends] if config else [],
        }

    def health_status(self) -> dict[str, Any]:
        health = self._lifecycle._health_checker
        if not health:
            return {"backends": {}}

        all_status = health.get_all_status()
        return {
            "backends": {name: status.value for name, status in all_status.items()}
        }

    def metrics(self) -> dict[str, Any]:
        return self._lifecycle.get_metrics().get_metrics()

    def _set_backend_enabled(
        self, name: str, enabled: bool, persist: bool
    ) -> dict[str, Any]:
        config = self._lifecycle.get_config()
        if not config:
            return {"success": False, "error": "No config loaded"}

        new_data = dict(config.data)
        new_servers = dict(new_data.get("mcpServers", {}))

        # Check active backends first, then disabled backends
        if name in new_servers:
            entry = dict(new_servers[name])
        else:
            # Look in disabled backends
            disabled = {b.name: b for b in config.disabled_backends}
            if name not in disabled:
                return {"success": False, "error": f"Backend '{name}' not found"}
            entry = dict(disabled[name].raw)

        entry["enabled"] = enabled
        new_servers[name] = entry
        new_data["mcpServers"] = new_servers

        self._write_config(config.path, new_data)
        self._lifecycle.rebuild_proxy()
        action = "enabled" if enabled else "disabled"
        return {"success": True, "message": f"Backend '{name}' {action}"}

    def _write_config(self, config_path: Path, data: dict[str, Any]) -> None:
        try:
            config_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            LOGGER.info("Config written to %s", config_path)
        except OSError as exc:
            LOGGER.warning("Failed to write config: %s", exc)
            raise
