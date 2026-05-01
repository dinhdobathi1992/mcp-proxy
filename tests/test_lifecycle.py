from __future__ import annotations

import json
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
