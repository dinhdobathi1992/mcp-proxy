"""Healthy-path aggregation tests for the mcp-proxy.

These tests spin up real fixture backends (stdio and http) and verify that
the proxy exposes the correct combined set of tools and prompts.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mcp_proxy.server import build_proxy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_names(proxy) -> list[str]:
    return asyncio.run(_async_tool_names(proxy))


async def _async_tool_names(proxy) -> list[str]:
    tools = await proxy.list_tools()
    return [t.name for t in tools]


def _prompt_names(proxy) -> list[str]:
    return asyncio.run(_async_prompt_names(proxy))


async def _async_prompt_names(proxy) -> list[str]:
    prompts = await proxy.list_prompts()
    return [p.name for p in prompts]


# ---------------------------------------------------------------------------
# Single stdio backend tests
# ---------------------------------------------------------------------------


class TestSingleStdioBackend:
    def test_proxy_builds_from_valid_config(self, stdio_config: Path):
        proxy, config = build_proxy(stdio_config, name="test-proxy")
        assert proxy is not None
        assert len(config.backends) == 1
        assert config.backends[0].name == "echo"

    def test_tools_are_discoverable(self, stdio_config: Path):
        proxy, _ = build_proxy(stdio_config, name="test-proxy")
        tools = _tool_names(proxy)
        assert "echo" in tools
        assert "add" in tools

    def test_prompts_are_discoverable(self, stdio_config: Path):
        proxy, _ = build_proxy(stdio_config, name="test-proxy")
        prompts = _prompt_names(proxy)
        assert "greet" in prompts

    def test_echo_tool_is_callable(self, stdio_config: Path):
        proxy, _ = build_proxy(stdio_config, name="test-proxy")

        async def call():
            result = await proxy.call_tool("echo", {"message": "hello"})
            return result

        result = asyncio.run(call())
        assert result is not None
        # FastMCP returns a list of content objects
        assert any("hello" in str(item) for item in result)

    def test_add_tool_returns_correct_sum(self, stdio_config: Path):
        proxy, _ = build_proxy(stdio_config, name="test-proxy")

        async def call():
            return await proxy.call_tool("add", {"a": 3, "b": 7})

        result = asyncio.run(call())
        assert any("10" in str(item) for item in result)


# ---------------------------------------------------------------------------
# Mixed stdio + http backend tests
# ---------------------------------------------------------------------------


class TestMixedBackends:
    def test_proxy_builds_with_both_backends(self, mixed_config: Path):
        proxy, config = build_proxy(mixed_config, name="mixed-proxy")
        assert len(config.backends) == 2
        backend_names = {b.name for b in config.backends}
        assert backend_names == {"echo", "math"}

    def test_all_tools_exposed_with_namespace_prefix(self, mixed_config: Path):
        proxy, _ = build_proxy(mixed_config, name="mixed-proxy")
        tools = _tool_names(proxy)
        # With multiple backends FastMCP prefixes: backend_name + "_" + tool_name
        assert "echo_echo" in tools
        assert "echo_add" in tools
        assert "math_multiply" in tools
        assert "math_subtract" in tools

    def test_prompts_from_both_backends_exposed(self, mixed_config: Path):
        proxy, _ = build_proxy(mixed_config, name="mixed-proxy")
        prompts = _prompt_names(proxy)
        assert "echo_greet" in prompts
        assert "math_math_intro" in prompts

    def test_stdio_tool_callable_through_mixed_proxy(self, mixed_config: Path):
        proxy, _ = build_proxy(mixed_config, name="mixed-proxy")

        async def call():
            return await proxy.call_tool("echo_echo", {"message": "proxied"})

        result = asyncio.run(call())
        assert any("proxied" in str(item) for item in result)

    def test_http_tool_callable_through_mixed_proxy(self, mixed_config: Path):
        proxy, _ = build_proxy(mixed_config, name="mixed-proxy")

        async def call():
            return await proxy.call_tool("math_multiply", {"a": 6, "b": 7})

        result = asyncio.run(call())
        assert any("42" in str(item) for item in result)

    def test_total_tool_count_is_combined(self, mixed_config: Path):
        proxy, _ = build_proxy(mixed_config, name="mixed-proxy")
        tools = _tool_names(proxy)
        # 2 from echo + 2 from math = 4
        assert len(tools) >= 4


# ---------------------------------------------------------------------------
# Proxy metadata tests
# ---------------------------------------------------------------------------


class TestProxyMetadata:
    def test_proxy_name_is_set(self, stdio_config: Path):
        proxy, _ = build_proxy(stdio_config, name="my-named-proxy")
        assert proxy.name == "my-named-proxy"

    def test_config_path_is_absolute(self, stdio_config: Path):
        _, config = build_proxy(stdio_config)
        assert config.path.is_absolute()

    def test_backend_transport_recorded_correctly(self, stdio_config: Path):
        _, config = build_proxy(stdio_config)
        assert config.backends[0].transport == "stdio"
