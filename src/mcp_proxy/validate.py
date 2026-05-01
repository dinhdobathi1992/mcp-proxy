from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import urlparse

VALID_BACKEND_TRANSPORTS = {"stdio", "http", "sse"}
VALID_FRONT_TRANSPORTS = {"stdio", "http"}


class ConfigError(ValueError):
    """Raised when proxy configuration is invalid."""


def normalize_and_validate_config(
    payload: Any,
    *,
    source_path: Path | None = None,
    strict_startup: bool = True,
) -> dict[str, Any]:
    """Normalize top-level config while preserving backend-specific fields."""

    if not isinstance(payload, Mapping):
        raise ConfigError("Config file must contain a JSON object at the top level.")

    raw_backends = payload.get("mcpServers")
    if not isinstance(raw_backends, Mapping) or not raw_backends:
        raise ConfigError("Config file must define a non-empty 'mcpServers' object.")

    all_backends: dict[str, Any] = {}
    active_backends: dict[str, Any] = {}
    for backend_name, backend_config in raw_backends.items():
        normalized = normalize_backend_config(
            str(backend_name),
            backend_config,
            source_path=source_path,
            strict_startup=strict_startup,
        )
        all_backends[str(backend_name)] = normalized
        if normalized.get("enabled", True):
            active_backends[str(backend_name)] = normalized

    if not active_backends:
        raise ConfigError(
            "Config file has no enabled backends. "
            "Set 'enabled': true on at least one backend."
        )

    return {"mcpServers": active_backends, "_all_backends": all_backends}


def normalize_backend_config(
    backend_name: str,
    backend_config: Any,
    *,
    source_path: Path | None = None,
    strict_startup: bool = True,
) -> dict[str, Any]:
    """Normalize one backend entry and reject clearly invalid shapes."""

    if not isinstance(backend_config, Mapping):
        raise ConfigError(f"Backend '{backend_name}' must be a JSON object.")

    normalized = dict(backend_config)

    # Validate and normalize the enabled flag before any other checks.
    enabled = normalized.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(
            f"Backend '{backend_name}' field 'enabled' must be a boolean (true/false)."
        )
    normalized["enabled"] = enabled

    # Disabled backends skip all further validation and startup checks.
    if not enabled:
        return normalized

    has_command = "command" in normalized
    has_url = "url" in normalized

    if has_command == has_url:
        raise ConfigError(
            f"Backend '{backend_name}' must define exactly one of 'command' or 'url'."
        )

    if has_command:
        normalized["command"] = _validate_command(backend_name, normalized.get("command"))
        normalized["args"] = _validate_string_list(
            backend_name,
            "args",
            normalized.get("args", []),
        )
        normalized["env"] = _validate_string_mapping(
            backend_name,
            "env",
            normalized.get("env", {}),
        )
        normalized["transport"] = _normalize_transport(
            backend_name,
            normalized.get("transport"),
            default_transport="stdio",
            allowed_transports={"stdio"},
        )
        if strict_startup:
            _validate_command_exists(
                normalized["command"],
                backend_name=backend_name,
                source_path=source_path,
            )
    else:
        normalized["url"] = _validate_url(backend_name, normalized.get("url"))
        normalized["headers"] = _validate_string_mapping(
            backend_name,
            "headers",
            normalized.get("headers", {}),
        )
        normalized["transport"] = _normalize_transport(
            backend_name,
            normalized.get("transport"),
            default_transport="http",
            allowed_transports={"http", "sse"},
        )

    if "cwd" in normalized:
        cwd = normalized["cwd"]
        if not isinstance(cwd, str) or not cwd.strip():
            raise ConfigError(
                f"Backend '{backend_name}' field 'cwd' must be a non-empty string."
            )
        cwd_path = Path(cwd).expanduser()
        if not cwd_path.is_absolute():
            cwd_path = (source_path.parent / cwd_path).resolve() if source_path else cwd_path.resolve()
        if not cwd_path.is_dir():
            raise ConfigError(
                f"Backend '{backend_name}' field 'cwd' must be an existing directory: {cwd_path}"
            )
        normalized["cwd"] = str(cwd_path)

    _validate_optional_positive_int(backend_name, "timeout", normalized.get("timeout"))
    return normalized


def validate_front_transport(transport: str) -> str:
    """Validate the transport used by the front proxy server."""

    normalized = transport.strip().lower()
    if normalized not in VALID_FRONT_TRANSPORTS:
        raise ConfigError(
            f"Unsupported front transport '{transport}'. "
            f"Expected one of: {sorted(VALID_FRONT_TRANSPORTS)}."
        )
    return normalized


def _normalize_transport(
    backend_name: str,
    transport: Any,
    *,
    default_transport: str,
    allowed_transports: set[str],
) -> str:
    if transport is None:
        return default_transport
    if not isinstance(transport, str):
        raise ConfigError(f"Backend '{backend_name}' transport must be a string.")

    normalized = transport.strip().lower()
    if normalized not in VALID_BACKEND_TRANSPORTS:
        raise ConfigError(
            f"Backend '{backend_name}' uses unsupported transport '{transport}'. "
            f"Expected one of: {sorted(VALID_BACKEND_TRANSPORTS)}."
        )
    if normalized not in allowed_transports:
        expected = ", ".join(sorted(allowed_transports))
        raise ConfigError(
            f"Backend '{backend_name}' transport '{normalized}' is not valid for this backend. "
            f"Expected: {expected}."
        )
    return normalized


def _validate_command(backend_name: str, command: Any) -> str:
    if not isinstance(command, str) or not command.strip():
        raise ConfigError(f"Backend '{backend_name}' command must be a non-empty string.")
    return command.strip()


def _validate_url(backend_name: str, url: Any) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ConfigError(f"Backend '{backend_name}' url must be a non-empty string.")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(
            f"Backend '{backend_name}' url must be a valid http or https URL."
        )
    return url


def _validate_string_list(backend_name: str, field_name: str, value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(
            f"Backend '{backend_name}' field '{field_name}' must be a list of strings."
        )
    return list(value)


def _validate_string_mapping(
    backend_name: str,
    field_name: str,
    value: Any,
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(
            f"Backend '{backend_name}' field '{field_name}' must be an object of string pairs."
        )

    result: dict[str, str] = {}
    for key, mapping_value in value.items():
        if not isinstance(key, str) or not isinstance(mapping_value, str):
            raise ConfigError(
                f"Backend '{backend_name}' field '{field_name}' must contain only string pairs."
            )
        result[key] = mapping_value
    return result


def _validate_optional_positive_int(
    backend_name: str,
    field_name: str,
    value: Any,
) -> None:
    if value is None:
        return
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(
            f"Backend '{backend_name}' field '{field_name}' must be a positive integer."
        )


def _validate_command_exists(
    command: str,
    *,
    backend_name: str,
    source_path: Path | None = None,
) -> None:
    command_path = Path(command).expanduser()
    if command_path.is_absolute() or "/" in command or "\\" in command:
        if command_path.is_absolute():
            candidate = command_path
        elif source_path is not None and not command_path.exists():
            candidate = (source_path.parent / command_path).resolve()
        else:
            candidate = command_path.resolve()
        if not candidate.exists():
            raise ConfigError(
                f"Backend '{backend_name}' command path does not exist: {candidate}"
            )
        return

    if shutil.which(command) is None:
        raise ConfigError(
            f"Backend '{backend_name}' command was not found on PATH: {command}"
        )
