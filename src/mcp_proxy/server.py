from __future__ import annotations

import os
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from .auth import APIKeyAuth, AuthMiddleware, RateLimiter, RateLimitMiddleware
from .config import ProxyConfig
from .lifecycle import ProxyLifecycleManager
from .logging import get_logger
from .validate import validate_front_transport

LOGGER = get_logger("server")


def _ui_runtime_dir() -> Path:
    """Return a per-user runtime dir for UI IPC files."""
    base = Path(tempfile.gettempdir()) / f"mcp-proxy-{os.getuid()}"
    base.mkdir(mode=0o700, exist_ok=True)
    try:
        base.chmod(0o700)
    except OSError:
        pass
    return base


def _ui_paths() -> tuple[Path, Path]:
    """Return unpredictable status + command paths under the runtime dir."""
    base = _ui_runtime_dir()
    token = secrets.token_hex(16)
    return (
        base / f"status-{token}.dat",
        base / f"commands-{token}.jsonl",
    )


def _drain_stream(stream: Any, label: str) -> None:
    """Read a child stream line-by-line and log each line at WARNING."""
    try:
        for raw in iter(stream.readline, b""):
            if not raw:
                break
            LOGGER.warning("%s: %s", label, raw.rstrip(b"\n").decode("utf-8", "replace"))
    except (ValueError, OSError):
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _start_ui_server(
    ui_port: int, status_path: str, command_path: str | None = None
) -> subprocess.Popen | None:
    """Start the UI server as a child process."""
    ui_dir = Path(__file__).parent.parent.parent / "ui" / "dist"
    try:
        cmd = [
            sys.executable, "-m", "mcp_proxy.ui_server",
            "--port", str(ui_port),
            "--status-path", status_path,
        ]
        if ui_dir.exists():
            cmd.extend(["--ui-dir", str(ui_dir)])
        if command_path:
            cmd.extend(["--command-path", command_path])
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        threading.Thread(
            target=_drain_stream,
            args=(proc.stderr, "ui_server"),
            daemon=True,
        ).start()
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


def _install_sighup(mgr: ProxyLifecycleManager) -> None:
    """Install a SIGHUP handler that triggers a config reload."""
    if not hasattr(signal, "SIGHUP"):
        return

    def _handler(signum: int, frame: object) -> None:
        LOGGER.info("Received SIGHUP, reloading config...")
        try:
            mgr.rebuild_proxy()
        except Exception as exc:
            LOGGER.warning("SIGHUP reload failed: %s", exc)

    try:
        signal.signal(signal.SIGHUP, _handler)
    except (ValueError, OSError):
        pass


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
    auth_api_key: str | None = None,
    rate_limit: int = 100,
) -> int:
    """Run the proxy using the selected front transport."""

    front_transport = validate_front_transport(transport)
    status_path, command_path = _ui_paths()
    mgr = ProxyLifecycleManager(
        config_path,
        name=name,
        strict_startup=strict_startup,
        watch=watch,
        health_interval=health_interval,
        ui_mode=ui_mode,
        ui_status_path=str(status_path),
        ui_command_path=str(command_path),
    )
    mgr.start()
    _install_sighup(mgr)

    proxy = mgr.get_proxy()
    config = mgr.get_config()
    backend_names = ", ".join(backend.name for backend in config.backends)

    ui_proc = None
    if ui_mode != "off":
        ui_command_arg = (
            str(mgr.get_ui_command_path()) if ui_mode == "advanced" else None
        )
        ui_proc = _start_ui_server(
            ui_port, str(mgr.get_ui_status_path()), ui_command_arg
        )

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
        run_kwargs: dict[str, Any] = {"transport": "http", "host": host, "port": port}
        if tls_cert and tls_key:
            run_kwargs["ssl_certfile"] = tls_cert
            run_kwargs["ssl_keyfile"] = tls_key

        middleware = _build_http_middleware(auth_api_key, rate_limit)
        if middleware:
            run_kwargs["middleware"] = middleware

        proxy.run(**run_kwargs)
        return 0
    finally:
        if ui_proc:
            ui_proc.terminate()
            try:
                ui_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ui_proc.kill()
        mgr.stop()


def _build_http_middleware(
    auth_api_key: str | None, rate_limit: int
) -> list[Any]:
    """Build the Starlette middleware stack for the front HTTP transport.

    Rate limit is the outermost layer so unauthenticated floods get rejected
    before the auth check; auth runs inside it on requests that pass the
    limit.
    """
    from starlette.middleware import Middleware

    layers: list[Any] = []
    if rate_limit and rate_limit > 0:
        layers.append(
            Middleware(RateLimitMiddleware, limiter=RateLimiter(max_requests=rate_limit))
        )
    if auth_api_key:
        layers.append(Middleware(AuthMiddleware, auth=APIKeyAuth(auth_api_key)))
    return layers
