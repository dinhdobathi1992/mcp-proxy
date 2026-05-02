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

    def test_remove_backend_runtime(self, make_config_file, python_exe, backend_stdio_path):
        config = make_config_file({
            "mcpServers": {
                "echo": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                },
                "echo2": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                },
            }
        })
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.remove_backend("echo")
        assert result["success"] is True
        assert "echo" not in [b.name for b in mgr.get_config().backends]
        mgr.stop()

    def test_disable_backend(self, make_config_file, python_exe, backend_stdio_path):
        config = make_config_file({
            "mcpServers": {
                "echo": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                },
                "echo2": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                },
            }
        })
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.disable_backend("echo2")
        assert result["success"] is True
        mgr.stop()

    def test_disable_last_enabled_rejected(self, stdio_config: Path):
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.disable_backend("echo")
        assert result["success"] is False
        assert "last enabled" in result["error"]
        mgr.stop()

    def test_enable_backend(self, make_config_file, python_exe, backend_stdio_path):
        config = make_config_file({
            "mcpServers": {
                "echo": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                },
                "echo2": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                    "enabled": False,
                },
            }
        })
        from mcp_proxy.lifecycle import ProxyLifecycleManager

        mgr = ProxyLifecycleManager(config, name="test", strict_startup=False, watch=False)
        mgr.start()
        tools = ManagementTools(mgr)

        result = tools.enable_backend("echo2")
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
