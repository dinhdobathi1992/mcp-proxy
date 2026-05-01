"""Unit tests for config loading and validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mcp_proxy.config import BackendConfig, ProxyConfig, load_config
from mcp_proxy.validate import ConfigError, normalize_and_validate_config


# ---------------------------------------------------------------------------
# normalize_and_validate_config unit tests
# ---------------------------------------------------------------------------


class TestNormalizeTopLevel:
    def test_requires_mapping(self):
        with pytest.raises(ConfigError, match="JSON object at the top level"):
            normalize_and_validate_config([])

    def test_requires_mcp_servers_key(self):
        with pytest.raises(ConfigError, match="'mcpServers'"):
            normalize_and_validate_config({})

    def test_empty_mcp_servers_is_rejected(self):
        with pytest.raises(ConfigError, match="non-empty"):
            normalize_and_validate_config({"mcpServers": {}})

    def test_mcp_servers_must_be_mapping(self):
        with pytest.raises(ConfigError, match="'mcpServers'"):
            normalize_and_validate_config({"mcpServers": "wrong"})


class TestNormalizeStdioBackend:
    def _valid(self, extra: dict | None = None) -> dict:
        base = {"mcpServers": {"be": {"command": sys.executable}}}
        if extra:
            base["mcpServers"]["be"].update(extra)
        return base

    def test_stdio_transport_defaulted(self):
        result = normalize_and_validate_config(self._valid(), strict_startup=False)
        assert result["mcpServers"]["be"]["transport"] == "stdio"

    def test_args_defaulted_to_empty_list(self):
        result = normalize_and_validate_config(self._valid(), strict_startup=False)
        assert result["mcpServers"]["be"]["args"] == []

    def test_env_defaulted_to_empty_dict(self):
        result = normalize_and_validate_config(self._valid(), strict_startup=False)
        assert result["mcpServers"]["be"]["env"] == {}

    def test_explicit_args_preserved(self):
        result = normalize_and_validate_config(
            self._valid({"args": ["--foo", "bar"]}), strict_startup=False
        )
        assert result["mcpServers"]["be"]["args"] == ["--foo", "bar"]

    def test_extra_fields_preserved(self):
        result = normalize_and_validate_config(
            self._valid({"cwd": "/tmp", "keep_alive": True}), strict_startup=False
        )
        assert result["mcpServers"]["be"]["cwd"] == "/tmp"
        assert result["mcpServers"]["be"]["keep_alive"] is True

    def test_invalid_command_type(self):
        with pytest.raises(ConfigError, match="command must be a non-empty string"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": 42}}}, strict_startup=False
            )

    def test_invalid_args_type(self):
        with pytest.raises(ConfigError, match="'args' must be a list of strings"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": "python3", "args": "bad"}}},
                strict_startup=False,
            )

    def test_invalid_env_type(self):
        with pytest.raises(ConfigError, match="must be an object of string pairs"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": "python3", "env": ["bad"]}}},
                strict_startup=False,
            )

    def test_non_string_env_values_rejected(self):
        with pytest.raises(ConfigError, match="must contain only string pairs"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": "python3", "env": {"K": 123}}}},
                strict_startup=False,
            )

    def test_http_transport_rejected_for_command_backend(self):
        with pytest.raises(ConfigError, match="not valid for this backend"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": "python3", "transport": "http"}}},
                strict_startup=False,
            )

    def test_command_and_url_both_present_rejected(self):
        with pytest.raises(ConfigError, match="exactly one of 'command' or 'url'"):
            normalize_and_validate_config(
                {
                    "mcpServers": {
                        "be": {"command": "python3", "url": "http://x.com/mcp"}
                    }
                },
                strict_startup=False,
            )

    def test_neither_command_nor_url_rejected(self):
        with pytest.raises(ConfigError, match="exactly one of 'command' or 'url'"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"foo": "bar"}}}, strict_startup=False
            )


class TestNormalizeHttpBackend:
    def _valid(self, extra: dict | None = None) -> dict:
        base = {"mcpServers": {"be": {"url": "http://127.0.0.1:9001/mcp"}}}
        if extra:
            base["mcpServers"]["be"].update(extra)
        return base

    def test_http_transport_defaulted(self):
        result = normalize_and_validate_config(self._valid())
        assert result["mcpServers"]["be"]["transport"] == "http"

    def test_sse_transport_accepted(self):
        result = normalize_and_validate_config(self._valid({"transport": "sse"}))
        assert result["mcpServers"]["be"]["transport"] == "sse"

    def test_stdio_transport_rejected_for_url_backend(self):
        with pytest.raises(ConfigError, match="not valid for this backend"):
            normalize_and_validate_config(self._valid({"transport": "stdio"}))

    def test_invalid_url_scheme(self):
        with pytest.raises(ConfigError, match="valid http or https URL"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"url": "ftp://bad.example.com/mcp"}}}
            )

    def test_malformed_url_rejected(self):
        with pytest.raises(ConfigError, match="valid http or https URL"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"url": "not-a-url"}}}
            )

    def test_headers_preserved(self):
        result = normalize_and_validate_config(
            self._valid({"headers": {"Authorization": "Bearer token"}})
        )
        assert result["mcpServers"]["be"]["headers"] == {"Authorization": "Bearer token"}

    def test_invalid_transport_value_rejected(self):
        with pytest.raises(ConfigError, match="unsupported transport"):
            normalize_and_validate_config(
                self._valid({"transport": "grpc"})
            )


class TestOptionalTimeout:
    def test_positive_timeout_accepted(self):
        payload = {
            "mcpServers": {"be": {"command": sys.executable, "timeout": 30}}
        }
        result = normalize_and_validate_config(payload, strict_startup=False)
        assert result["mcpServers"]["be"]["timeout"] == 30

    def test_zero_timeout_rejected(self):
        with pytest.raises(ConfigError, match="positive integer"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "timeout": 0}}},
                strict_startup=False,
            )

    def test_negative_timeout_rejected(self):
        with pytest.raises(ConfigError, match="positive integer"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "timeout": -1}}},
                strict_startup=False,
            )


class TestStrictStartup:
    def test_missing_executable_fails_in_strict_mode(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="command path does not exist"):
            normalize_and_validate_config(
                {
                    "mcpServers": {
                        "be": {
                            "command": str(tmp_path / "nonexistent_binary"),
                        }
                    }
                },
                strict_startup=True,
            )

    def test_missing_path_command_not_on_path_fails(self):
        with pytest.raises(ConfigError, match="not found on PATH"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": "does_not_exist_binary_xyz"}}},
                strict_startup=True,
            )

    def test_missing_command_allowed_when_not_strict(self):
        result = normalize_and_validate_config(
            {"mcpServers": {"be": {"command": "does_not_exist_binary_xyz"}}},
            strict_startup=False,
        )
        assert result["mcpServers"]["be"]["command"] == "does_not_exist_binary_xyz"


# ---------------------------------------------------------------------------
# load_config integration tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_valid_stdio_config(
        self, make_config_file, python_exe: str, backend_stdio_path: Path
    ):
        path = make_config_file(
            {
                "mcpServers": {
                    "echo": {"command": python_exe, "args": [str(backend_stdio_path)]}
                }
            }
        )
        config = load_config(path)
        assert isinstance(config, ProxyConfig)
        assert len(config.backends) == 1
        backend = config.backends[0]
        assert isinstance(backend, BackendConfig)
        assert backend.name == "echo"
        assert backend.transport == "stdio"

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="does not exist"):
            load_config(tmp_path / "missing.json")

    def test_load_invalid_json_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid JSON"):
            load_config(bad)

    def test_load_preserves_backend_count(
        self, make_config_file, python_exe: str, backend_stdio_path: Path
    ):
        path = make_config_file(
            {
                "mcpServers": {
                    "a": {"command": python_exe, "args": [str(backend_stdio_path)]},
                    "b": {"url": "http://127.0.0.1:9999/mcp"},
                }
            }
        )
        config = load_config(path, strict_startup=False)
        assert len(config.backends) == 2
        names = {b.name for b in config.backends}
        assert names == {"a", "b"}

    def test_path_is_absolute_in_result(
        self, make_config_file, python_exe: str, backend_stdio_path: Path
    ):
        path = make_config_file(
            {
                "mcpServers": {
                    "echo": {"command": python_exe, "args": [str(backend_stdio_path)]}
                }
            }
        )
        config = load_config(path)
        assert config.path.is_absolute()


# ---------------------------------------------------------------------------
# enabled flag tests
# ---------------------------------------------------------------------------


class TestEnabledFlag:
    def test_enabled_true_is_accepted(self):
        result = normalize_and_validate_config(
            {"mcpServers": {"be": {"command": sys.executable, "enabled": True}}},
            strict_startup=False,
        )
        assert result["mcpServers"]["be"]["enabled"] is True

    def test_enabled_false_skips_validation_and_startup_checks(self):
        # A disabled backend with a missing command should NOT raise.
        result = normalize_and_validate_config(
            {
                "mcpServers": {
                    "active": {"command": sys.executable},
                    "broken": {"command": "nonexistent_xyz", "enabled": False},
                }
            },
            strict_startup=True,
        )
        assert "broken" not in result["mcpServers"]
        assert "active" in result["mcpServers"]

    def test_enabled_false_excluded_from_active_backends(self):
        result = normalize_and_validate_config(
            {
                "mcpServers": {
                    "active": {"command": sys.executable, "enabled": True},
                    "inactive": {"command": sys.executable, "enabled": False},
                }
            },
            strict_startup=False,
        )
        assert "active" in result["mcpServers"]
        assert "inactive" not in result["mcpServers"]

    def test_all_disabled_raises(self):
        with pytest.raises(ConfigError, match="no enabled backends"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "enabled": False}}},
                strict_startup=False,
            )

    def test_enabled_non_bool_rejected(self):
        with pytest.raises(ConfigError, match="'enabled' must be a boolean"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "enabled": "yes"}}},
                strict_startup=False,
            )

    def test_enabled_default_is_true(self):
        result = normalize_and_validate_config(
            {"mcpServers": {"be": {"command": sys.executable}}},
            strict_startup=False,
        )
        assert result["mcpServers"]["be"]["enabled"] is True

    def test_load_config_disabled_backends_tracked(
        self, make_config_file, python_exe: str, backend_stdio_path: Path
    ):
        path = make_config_file(
            {
                "mcpServers": {
                    "on":  {"command": python_exe, "args": [str(backend_stdio_path)]},
                    "off": {"command": python_exe, "enabled": False},
                }
            }
        )
        config = load_config(path, strict_startup=False)
        assert len(config.backends) == 1
        assert config.backends[0].name == "on"
        assert len(config.disabled_backends) == 1
        assert config.disabled_backends[0].name == "off"
        assert config.disabled_backends[0].enabled is False


# ---------------------------------------------------------------------------
# cwd validation tests
# ---------------------------------------------------------------------------


class TestCwdValidation:
    def test_valid_cwd_accepted(self, tmp_path: Path):
        result = normalize_and_validate_config(
            {"mcpServers": {"be": {"command": sys.executable, "cwd": str(tmp_path)}}},
            strict_startup=False,
        )
        assert result["mcpServers"]["be"]["cwd"] == str(tmp_path)

    def test_invalid_cwd_rejected(self):
        with pytest.raises(ConfigError, match="must be an existing directory"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "cwd": "/nonexistent/path"}}},
                strict_startup=False,
            )

    def test_cwd_relative_path_resolved(self, tmp_path: Path, make_config_file):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        config_path = make_config_file(
            {"mcpServers": {"be": {"command": sys.executable, "cwd": "subdir"}}}
        )
        result = normalize_and_validate_config(
            {"mcpServers": {"be": {"command": sys.executable, "cwd": "subdir"}}},
            source_path=config_path,
            strict_startup=False,
        )
        assert Path(result["mcpServers"]["be"]["cwd"]).is_absolute()
        assert result["mcpServers"]["be"]["cwd"] == str(subdir)

    def test_cwd_empty_string_rejected(self):
        with pytest.raises(ConfigError, match="must be a non-empty string"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "cwd": "  "}}},
                strict_startup=False,
            )

    def test_cwd_non_string_rejected(self):
        with pytest.raises(ConfigError, match="must be a non-empty string"):
            normalize_and_validate_config(
                {"mcpServers": {"be": {"command": sys.executable, "cwd": 123}}},
                strict_startup=False,
            )
