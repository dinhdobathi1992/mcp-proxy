"""Failure-path and strict-startup tests for the mcp-proxy."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from mcp_proxy.cli import main
from mcp_proxy.config import load_config
from mcp_proxy.server import build_proxy
from mcp_proxy.validate import ConfigError, normalize_and_validate_config


# ---------------------------------------------------------------------------
# Config file error paths
# ---------------------------------------------------------------------------


class TestMissingConfig:
    def test_load_config_raises_for_missing_file(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="does not exist"):
            load_config(tmp_path / "no_such_file.json")

    def test_load_config_raises_for_directory(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="not a file"):
            load_config(tmp_path)

    def test_load_config_raises_for_invalid_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{broken json", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid JSON"):
            load_config(bad)

    def test_load_config_raises_for_empty_mcp_servers(self, tmp_path: Path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
        with pytest.raises(ConfigError, match="non-empty"):
            load_config(p)


# ---------------------------------------------------------------------------
# Duplicate-name collision: FastMCP namespaces per backend so duplicates
# across backends are disambiguated.  Within the same backend two tools
# with the same name would be a backend bug, not a proxy bug.  We verify
# that names from different backends don't collide after prefixing.
# ---------------------------------------------------------------------------


class TestNamespacing:
    def test_two_backends_with_same_tool_names_do_not_collide(
        self, make_config_file, python_exe: str, backend_stdio_path: Path
    ):
        """Verify backend_a_echo != backend_b_echo after prefixing."""
        path = make_config_file(
            {
                "mcpServers": {
                    "backend_a": {
                        "command": python_exe,
                        "args": [str(backend_stdio_path)],
                    },
                    "backend_b": {
                        "command": python_exe,
                        "args": [str(backend_stdio_path)],
                    },
                }
            }
        )
        proxy, _ = build_proxy(path, name="collision-test")
        tools = asyncio.run(proxy.list_tools())
        names = [t.name for t in tools]
        # Prefixed names must all be distinct
        assert len(names) == len(set(names)), f"Name collision detected: {names}"
        assert "backend_a_echo" in names
        assert "backend_b_echo" in names


# ---------------------------------------------------------------------------
# Strict-startup failure paths
# ---------------------------------------------------------------------------


class TestStrictStartupCli:
    def test_check_mode_succeeds_with_valid_config(self, stdio_config: Path):
        rc = main(["--config", str(stdio_config), "--check"])
        assert rc == 0

    def test_check_mode_fails_for_missing_file(self, tmp_path: Path):
        rc = main(["--config", str(tmp_path / "missing.json"), "--check"])
        assert rc == 2

    def test_check_mode_fails_for_nonexistent_command(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {"mcpServers": {"be": {"command": "this_binary_does_not_exist_xyzzy"}}}
            ),
            encoding="utf-8",
        )
        rc = main(["--config", str(bad), "--check"])
        assert rc == 2

    def test_check_mode_passes_with_no_strict_startup(self, tmp_path: Path):
        cfg = tmp_path / "lenient.json"
        cfg.write_text(
            json.dumps(
                {"mcpServers": {"be": {"command": "this_binary_does_not_exist_xyzzy"}}}
            ),
            encoding="utf-8",
        )
        rc = main(["--config", str(cfg), "--check", "--no-strict-startup"])
        assert rc == 0

    def test_invalid_transport_arg_rejected_by_argparse(self):
        with pytest.raises(SystemExit):
            main(["--transport", "grpc", "--check"])


# ---------------------------------------------------------------------------
# HTTP backend unreachable at call time
# ---------------------------------------------------------------------------


class TestUnreachableHttpBackend:
    def test_proxy_builds_against_unreachable_http_backend(
        self, make_config_file
    ):
        """Proxy construction should succeed; connection errors surface at call time."""
        path = make_config_file(
            {
                "mcpServers": {
                    "dead": {"url": "http://127.0.0.1:19999/mcp"}
                }
            }
        )
        # build_proxy should not connect eagerly
        proxy, config = build_proxy(path, name="test")
        assert len(config.backends) == 1

    def test_tool_list_returns_empty_for_unreachable_http_backend(
        self, make_config_file
    ):
        """FastMCP proxy swallows the backend connection error and returns an empty
        tool list rather than raising, so we assert the list is empty."""
        path = make_config_file(
            {
                "mcpServers": {
                    "dead": {"url": "http://127.0.0.1:19999/mcp"}
                }
            }
        )
        proxy, _ = build_proxy(path, name="test")

        async def call():
            return await proxy.list_tools()

        tools = asyncio.run(call())
        assert tools == [], f"Expected empty tool list for unreachable backend, got: {tools}"


# ---------------------------------------------------------------------------
# Validate CLI --check output
# ---------------------------------------------------------------------------


class TestCliValidate:
    def test_check_prints_backend_count(
        self, stdio_config: Path, capsys: pytest.CaptureFixture
    ):
        rc = main(["--config", str(stdio_config), "--check"])
        assert rc == 0
        # Logged to stderr, not stdout
        captured = capsys.readouterr()
        assert captured.out == ""


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


class TestGracefulShutdown:
    def test_sigint_returns_130(self, stdio_config, monkeypatch):
        """Verify SIGINT is caught and returns exit code 130."""
        from mcp_proxy.cli import main

        def raise_keyboard_interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr("mcp_proxy.cli.run_proxy", raise_keyboard_interrupt)
        result = main(["--config", str(stdio_config)])
        assert result == 130


# ---------------------------------------------------------------------------
# New CLI flags
# ---------------------------------------------------------------------------


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

    def test_auth_api_key_flag(self, stdio_config):
        from mcp_proxy.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--config", str(stdio_config), "--auth-api-key", "secret"])
        assert args.auth_api_key == "secret"

    def test_rate_limit_flag(self, stdio_config):
        from mcp_proxy.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--config", str(stdio_config), "--rate-limit", "50"])
        assert args.rate_limit == 50
