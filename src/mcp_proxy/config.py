from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .validate import ConfigError, normalize_and_validate_config


@dataclass(frozen=True, slots=True)
class BackendConfig:
    """Normalized downstream backend definition."""

    name: str
    transport: str
    enabled: bool
    cwd: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Loaded proxy configuration and normalized downstream backends."""

    path: Path
    data: dict[str, Any]
    backends: tuple[BackendConfig, ...]
    disabled_backends: tuple[BackendConfig, ...]


def load_config(path: str | Path, *, strict_startup: bool = True) -> ProxyConfig:
    """Load and normalize the JSON config file used by the proxy."""

    config_path = Path(path).expanduser()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"Config path is not a file: {config_path}")

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Config file is not valid JSON: {config_path} ({exc.msg})"
        ) from exc

    normalized = normalize_and_validate_config(
        payload,
        source_path=config_path,
        strict_startup=strict_startup,
    )
    all_backends = normalized.pop("_all_backends")
    backends = tuple(
        BackendConfig(name=name, transport=backend["transport"], enabled=True, cwd=backend.get("cwd"), raw=backend)
        for name, backend in normalized["mcpServers"].items()
    )
    disabled_backends = tuple(
        BackendConfig(name=name, transport=backend.get("transport", ""), enabled=False, cwd=backend.get("cwd"), raw=backend)
        for name, backend in all_backends.items()
        if not backend.get("enabled", True)
    )
    return ProxyConfig(
        path=config_path,
        data=normalized,
        backends=backends,
        disabled_backends=disabled_backends,
    )
