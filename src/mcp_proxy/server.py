from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import ProxyConfig
from .lifecycle import ProxyLifecycleManager
from .logging import get_logger
from .validate import validate_front_transport

LOGGER = get_logger("server")


def _start_ui_server(ui_port: int, status_path: str) -> subprocess.Popen | None:
    """Start the UI server as a child process."""
    # Find the Vue build output
    ui_dir = Path(__file__).parent.parent.parent / "ui" / "dist"
    try:
        cmd = [
            sys.executable, "-m", "mcp_proxy.ui_server",
            "--port", str(ui_port),
            "--status-path", status_path,
        ]
        if ui_dir.exists():
            cmd.extend(["--ui-dir", str(ui_dir)])
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        LOGGER.info("UI server started on port %s (PID: %s)", ui_port, proc.pid)
        return proc
    except Exception as exc:
        LOGGER.warning("Failed to start UI server: %s", exc)
        return None


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
    tls_cert: str | None = None,
    tls_key: str | None = None,
    ui_mode: str = "off",
    ui_port: int = 8080,
) -> int:
    """Run the proxy using the selected front transport."""

    front_transport = validate_front_transport(transport)
    mgr = ProxyLifecycleManager(
        config_path,
        name=name,
        strict_startup=strict_startup,
        watch=watch,
        health_interval=health_interval,
        ui_mode=ui_mode,
        ui_status_path=f"/tmp/mcp-proxy-status-{os.getpid()}.dat",
        ui_command_path=f"/tmp/mcp-proxy-commands-{os.getpid()}.jsonl",
    )
    mgr.start()

    proxy = mgr.get_proxy()
    config = mgr.get_config()
    backend_names = ", ".join(backend.name for backend in config.backends)

    ui_proc = None
    if ui_mode != "off":
        ui_proc = _start_ui_server(ui_port, mgr._ui_status_path)

    try:
        if front_transport == "stdio":
            LOGGER.info(
                "Starting MCP proxy via stdio with %d backend(s): %s",
                len(config.backends),
                backend_names,
            )
            proxy.run(transport="stdio")
            return 0

        LOGGER.info(
            "Starting MCP proxy via %s on %s:%s with %d backend(s): %s",
            "https" if tls_cert else "http",
            host,
            port,
            len(config.backends),
            backend_names,
        )
        if tls_cert and tls_key:
            proxy.run(transport="http", host=host, port=port, ssl_certfile=tls_cert, ssl_keyfile=tls_key)
        else:
            proxy.run(transport="http", host=host, port=port)
        return 0
    finally:
        if ui_proc:
            ui_proc.terminate()
            try:
                ui_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ui_proc.kill()
