from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ProxyConfig
from .lifecycle import ProxyLifecycleManager
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
    mgr = ProxyLifecycleManager(
        config_path, name=name, strict_startup=strict_startup
    )
    mgr.start()
    return mgr.get_proxy(), mgr.get_config()


def run_proxy(
    config_path: str | Path,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    name: str = "mcp-proxy",
    strict_startup: bool = True,
    watch: bool = False,
    health_interval: float = 30.0,
) -> int:
    """Run the proxy using the selected front transport."""

    front_transport = validate_front_transport(transport)
    mgr = ProxyLifecycleManager(
        config_path,
        name=name,
        strict_startup=strict_startup,
        watch=watch,
        health_interval=health_interval,
    )
    mgr.start()

    proxy = mgr.get_proxy()
    config = mgr.get_config()
    backend_names = ", ".join(backend.name for backend in config.backends)

    if front_transport == "stdio":
        LOGGER.info(
            "Starting MCP proxy via stdio with %d backend(s): %s",
            len(config.backends),
            backend_names,
        )
        proxy.run(transport="stdio")
        return 0

    LOGGER.info(
        "Starting MCP proxy via http on %s:%s with %d backend(s): %s",
        host,
        port,
        len(config.backends),
        backend_names,
    )
    proxy.run(transport="http", host=host, port=port)
    return 0
