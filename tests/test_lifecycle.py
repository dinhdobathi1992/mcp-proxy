from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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

        stdio_config.write_text("not json")

        mgr.rebuild_proxy()
        assert mgr.get_proxy() is original_proxy
        mgr.stop()

    def test_get_proxy_thread_safe(self, stdio_config: Path):
        mgr = ProxyLifecycleManager(stdio_config, name="test", watch=False)
        mgr.start()
        proxy1 = mgr.get_proxy()
        proxy2 = mgr.get_proxy()
        assert proxy1 is proxy2
        mgr.stop()


class TestProxyLifecycleManagerUI:
    def test_default_ui_mode_is_off(self, stdio_config: Path):
        mgr = ProxyLifecycleManager(stdio_config, name="test")
        assert mgr._ui_mode == "off"
        assert mgr._ui_writer is None
        assert mgr._ui_reader is None

    def test_ui_writer_starts_in_default_mode(self, stdio_config: Path, tmp_path):
        status_path = tmp_path / "status.bin"
        mgr = ProxyLifecycleManager(
            stdio_config,
            name="test",
            ui_mode="default",
            ui_status_path=status_path,
            ui_update_interval=1.0,
        )
        mgr.start()
        assert mgr._ui_writer is not None
        assert mgr._ui_thread is not None
        assert mgr._ui_thread.is_alive()
        assert mgr._ui_reader is None
        thread = mgr._ui_thread
        mgr.stop()
        assert not thread.is_alive()

    def test_ui_reader_starts_in_advanced_mode(self, stdio_config: Path, tmp_path):
        status_path = tmp_path / "status.bin"
        command_path = tmp_path / "commands.jsonl"
        command_path.write_text("")
        mgr = ProxyLifecycleManager(
            stdio_config,
            name="test",
            ui_mode="advanced",
            ui_status_path=status_path,
            ui_command_path=command_path,
            ui_update_interval=1.0,
        )
        mgr.start()
        assert mgr._ui_writer is not None
        assert mgr._ui_reader is not None
        assert mgr._ui_thread is not None
        assert mgr._ui_command_thread is not None
        assert mgr._ui_command_thread.is_alive()
        mgr.stop()

    def test_ui_writer_writes_status_file(self, stdio_config: Path, tmp_path):
        import struct

        status_path = tmp_path / "status.bin"
        mgr = ProxyLifecycleManager(
            stdio_config,
            name="test",
            ui_mode="default",
            ui_status_path=status_path,
            ui_update_interval=0.1,
        )
        mgr.start()

        import time
        time.sleep(0.3)

        assert status_path.exists()
        raw = status_path.read_bytes()
        size = struct.unpack("<I", raw[:4])[0]
        payload = json.loads(raw[4 : 4 + size])
        assert payload["proxy_name"] == "test"
        assert "backends" in payload
        assert "totals" in payload
        assert "timestamp" in payload
        mgr.stop()

    def test_execute_ui_command_enable_backend(self, stdio_config: Path, tmp_path):
        status_path = tmp_path / "status.bin"
        command_path = tmp_path / "commands.jsonl"
        command_path.write_text("")
        mgr = ProxyLifecycleManager(
            stdio_config,
            name="test",
            ui_mode="advanced",
            ui_status_path=status_path,
            ui_command_path=command_path,
            ui_update_interval=0.1,
        )
        mgr.start()

        with patch("mcp_proxy.lifecycle.ManagementTools") as mock_cls:
            mock_tools = MagicMock()
            mock_cls.return_value = mock_tools
            mock_tools.enable_backend.return_value = {"status": "ok"}

            cmd = {"action": "enable_backend", "args": {"name": "echo"}}
            mgr._execute_ui_command(cmd)
            mock_tools.enable_backend.assert_called_once_with("echo")

        mgr.stop()

    def test_execute_ui_command_reload_config(self, stdio_config: Path, tmp_path):
        status_path = tmp_path / "status.bin"
        command_path = tmp_path / "commands.jsonl"
        mgr = ProxyLifecycleManager(
            stdio_config,
            name="test",
            ui_mode="advanced",
            ui_status_path=status_path,
            ui_command_path=command_path,
            ui_update_interval=0.1,
        )
        mgr.start()

        with patch("mcp_proxy.lifecycle.ManagementTools") as mock_cls:
            mock_tools = MagicMock()
            mock_cls.return_value = mock_tools
            mock_tools.reload_config.return_value = {"status": "ok"}

            mgr._execute_ui_command({"action": "reload_config", "args": {}})
            mock_tools.reload_config.assert_called_once()

        mgr.stop()

    def test_execute_ui_command_unknown_logs_warning(self, stdio_config: Path, tmp_path):
        status_path = tmp_path / "status.bin"
        command_path = tmp_path / "commands.jsonl"
        mgr = ProxyLifecycleManager(
            stdio_config,
            name="test",
            ui_mode="advanced",
            ui_status_path=status_path,
            ui_command_path=command_path,
            ui_update_interval=0.1,
        )
        mgr.start()

        with patch("mcp_proxy.lifecycle.LOGGER") as mock_logger:
            mgr._execute_ui_command({"action": "unknown_action", "args": {}})
            mock_logger.warning.assert_called()

        mgr.stop()
