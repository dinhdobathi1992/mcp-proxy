from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ProxyConfig, load_config
from .logging import get_logger
from .validate import validate_front_transport

LOGGER = get_logger("server")


def build_proxy(
    config_path: str | Path,
    *,
    name: str = "mcp-proxy",
    strict_startup: bool = True,
) -> tuple[Any, ProxyConfig]:
    """Load config and build the FastMCP proxy instance."""

    proxy_config = load_config(config_path, strict_startup=strict_startup)

    if proxy_config.disabled_backends:
        disabled_names = ", ".join(b.name for b in proxy_config.disabled_backends)
        LOGGER.info("Skipping disabled backend(s): %s", disabled_names)

    from fastmcp.server import create_proxy

    proxy = create_proxy(proxy_config.data, name=name)
    return proxy, proxy_config


def run_proxy(
    config_path: str | Path,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    name: str = "mcp-proxy",
    strict_startup: bool = True,
) -> int:
    """Run the proxy using the selected front transport."""

    front_transport = validate_front_transport(transport)
    proxy, proxy_config = build_proxy(
        config_path,
        name=name,
        strict_startup=strict_startup,
    )
    backend_names = ", ".join(backend.name for backend in proxy_config.backends)

    if front_transport == "stdio":
        LOGGER.info(
            "Starting MCP proxy via stdio with %d backend(s): %s",
            len(proxy_config.backends),
            backend_names,
        )
        proxy.run(transport="stdio")
        return 0

    LOGGER.info(
        "Starting MCP proxy via http on %s:%s with %d backend(s): %s",
        host,
        port,
        len(proxy_config.backends),
        backend_names,
    )
    proxy.run(transport="http", host=host, port=port)
    return 0
