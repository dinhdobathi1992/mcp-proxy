from __future__ import annotations

import asyncio
import hmac
import json
import os
import struct
from pathlib import Path
from typing import Any

from aiohttp import web

from .logging import get_logger

LOGGER = get_logger("ui_server")


class UIServer:
    """Serves the management UI via HTTP and WebSocket."""

    def __init__(
        self,
        *,
        status_path: str,
        port: int = 8080,
        host: str = "127.0.0.1",
        ui_dir: str | None = None,
        command_path: str | None = None,
        api_token: str | None = None,
        ws_poll_interval: float = 2.0,
    ) -> None:
        self._status_path = Path(status_path)
        self._port = port
        self._host = host
        self._ui_dir = Path(ui_dir).resolve() if ui_dir else None
        self._command_path = Path(command_path) if command_path else None
        self._api_token = api_token
        self._ws_poll_interval = ws_poll_interval

    def read_status(self) -> dict[str, Any] | None:
        """Read status snapshot from the file."""
        if not self._status_path.exists():
            return None
        try:
            raw = self._status_path.read_bytes()
            if len(raw) < 4:
                return None
            size = struct.unpack("<I", raw[:4])[0]
            payload = raw[4 : 4 + size]
            return json.loads(payload)
        except (OSError, json.JSONDecodeError, struct.error) as exc:
            LOGGER.warning("Failed to read status file: %s", exc)
            return None

    def write_command(self, command: dict[str, Any]) -> None:
        """Append a command to the JSONL command file.

        Uses ``os.O_APPEND`` with a single ``write`` so concurrent appenders
        do not interleave bytes. POSIX guarantees atomicity for writes
        smaller than ``PIPE_BUF`` on append-mode descriptors.
        """
        if self._command_path is None:
            raise ValueError("No command path configured")
        payload = (json.dumps(command) + "\n").encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(str(self._command_path), flags, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)

    def run(self) -> None:
        """Start the UI server (blocking)."""
        app = web.Application()
        app.router.add_get("/api/status", self._handle_status)
        app.router.add_post("/api/command", self._handle_command)
        app.router.add_get("/ws", self._handle_websocket)

        if self._ui_dir and self._ui_dir.exists():
            app.router.add_get("/", self._handle_index)
            app.router.add_get("/{path:.*}", self._handle_static)

        web.run_app(app, host=self._host, port=self._port, print=None)

    def _check_auth(self, request: web.Request) -> bool:
        """Validate Bearer token from header or ``?token=`` query param.

        Browsers cannot set custom headers on WebSocket handshake requests,
        so we accept the token via query string as a fallback. Both paths
        use constant-time comparison.
        """
        if self._api_token is None:
            return True
        header = request.headers.get("Authorization", "")
        parts = header.split(" ", 1)
        if len(parts) == 2 and parts[0] == "Bearer":
            if hmac.compare_digest(parts[1], self._api_token):
                return True
        token = request.query.get("token")
        if token and hmac.compare_digest(token, self._api_token):
            return True
        return False

    async def _handle_index(self, request: web.Request) -> web.StreamResponse:
        return web.FileResponse(self._ui_dir / "index.html")

    async def _handle_static(self, request: web.Request) -> web.StreamResponse:
        path = request.match_info.get("path", "")
        ui_root = self._ui_dir
        try:
            requested = (ui_root / path).resolve()
            requested.relative_to(ui_root)
        except (ValueError, OSError):
            return web.Response(status=403, text="Forbidden")
        if requested.exists() and requested.is_file():
            return web.FileResponse(requested)
        index_path = ui_root / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(status=404, text="Not Found")

    async def _handle_status(self, request: web.Request) -> web.StreamResponse:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        status = self.read_status()
        if status is None:
            return web.json_response({"error": "No status available"}, status=503)
        return web.json_response(status)

    async def _handle_command(self, request: web.Request) -> web.StreamResponse:
        if not self._check_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        if self._command_path is None:
            return web.json_response(
                {"error": "Commands not supported (advanced mode only)"}, status=400
            )

        action = body.get("action")
        if not action:
            return web.json_response({"error": "Missing 'action' field"}, status=400)

        try:
            self.write_command(body)
            return web.json_response({"success": True, "message": f"Command '{action}' queued"})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    async def _handle_websocket(self, request: web.Request) -> web.StreamResponse:
        if not self._check_auth(request):
            return web.Response(status=401, text="Unauthorized")
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        try:
            while not ws.closed:
                status = self.read_status()
                if status:
                    await ws.send_json(status)
                await asyncio.sleep(self._ws_poll_interval)
        except (asyncio.CancelledError, ConnectionError):
            pass
        finally:
            await ws.close()
        return ws


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="MCP Proxy UI Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--status-path", required=True)
    parser.add_argument("--ui-dir", default=None)
    parser.add_argument("--command-path", default=None)
    args = parser.parse_args()

    server = UIServer(
        status_path=args.status_path,
        port=args.port,
        host=args.host,
        ui_dir=args.ui_dir,
        command_path=args.command_path,
        api_token=os.environ.get("MCP_PROXY_UI_TOKEN"),
    )
    server.run()
