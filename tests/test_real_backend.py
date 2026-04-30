"""Integration tests against the real devops-starter MCP backend.

These tests require the devops-starter server to be launchable via the
path configured in ~/.cursor/mcp.json. They are marked with the 'integration'
marker and are skipped by default unless --run-integration is passed.

Run them explicitly with:
    pytest tests/test_real_backend.py -v
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mcp_proxy.server import build_proxy


DEVOPS_PYTHON = "/Users/thi/Devops/thi-mcp/venv/bin/python"
DEVOPS_CWD = "/Users/thi/Devops/thi-mcp"


def _devops_starter_available() -> bool:
    """Return True if the devops-starter python venv exists."""
    return Path(DEVOPS_PYTHON).exists()


pytestmark = pytest.mark.skipif(
    not _devops_starter_available(),
    reason="devops-starter venv not found at expected path",
)


@pytest.fixture(scope="module")
def devops_config(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a proxy config pointing to the real devops-starter MCP backend."""
    tmp = tmp_path_factory.mktemp("real")
    p = tmp / "servers.json"
    p.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "devops": {
                        "command": DEVOPS_PYTHON,
                        "args": ["-m", "mcp_devops_starter"],
                        "cwd": DEVOPS_CWD,
                        "env": {"PYTHONPATH": DEVOPS_CWD},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return p


class TestRealDevopsBackend:
    def test_proxy_builds_against_real_backend(self, devops_config: Path):
        proxy, config = build_proxy(devops_config, name="real-test")
        assert proxy is not None
        assert len(config.backends) == 1
        assert config.backends[0].name == "devops"
        assert config.backends[0].transport == "stdio"

    def test_tools_discoverable_from_real_backend(self, devops_config: Path):
        proxy, _ = build_proxy(devops_config, name="real-test")

        async def list():
            tools = await proxy.list_tools()
            return [t.name for t in tools]

        tools = asyncio.run(list())
        assert len(tools) > 0, "Expected at least one tool from devops-starter"

    def test_git_status_tool_present(self, devops_config: Path):
        """devops-starter is known to expose a git_status tool."""
        proxy, _ = build_proxy(devops_config, name="real-test")

        async def list():
            tools = await proxy.list_tools()
            return [t.name for t in tools]

        tools = asyncio.run(list())
        assert any("git_status" in t for t in tools), (
            f"git_status not found in tools: {tools}"
        )

    def test_hello_devops_tool_callable(self, devops_config: Path):
        """hello_devops is a simple no-side-effect tool good for connectivity tests."""
        proxy, _ = build_proxy(devops_config, name="real-test")

        async def call():
            tools = await proxy.list_tools()
            tool_names = [t.name for t in tools]
            hello_tool = next(
                (t for t in tool_names if "hello" in t.lower()), None
            )
            if hello_tool is None:
                pytest.skip("hello_devops tool not present in this backend version")
            return await proxy.call_tool(hello_tool, {"name": "mcp-proxy"})

        result = asyncio.run(call())
        assert result is not None
