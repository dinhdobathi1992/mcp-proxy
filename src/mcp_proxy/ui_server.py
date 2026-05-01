from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .logging import get_logger

LOGGER = get_logger("ui_server")


class UIServer:
    """Serves the management UI via HTTP and WebSocket."""

    def __init__(
        self,
        *,
        status_path: str,
        port: int = 8080,
        ui_dir: str | None = None,
        command_path: str | None = None,
    ) -> None:
        self._status_path = Path(status_path)
        self._port = port
        self._ui_dir = Path(ui_dir) if ui_dir else None
        self._command_path = Path(command_path) if command_path else None

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
        """Append a command to the JSONL command file."""
        if self._command_path is None:
            raise ValueError("No command path configured")
        line = json.dumps(command) + "\n"
        with open(self._command_path, "a", encoding="utf-8") as f:
            f.write(line)

    def run(self) -> None:
        """Start the UI server (blocking)."""
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/api/status", self._handle_status)
        app.router.add_post("/api/command", self._handle_command)
        app.router.add_get("/ws", self._handle_websocket)

        if self._ui_dir and self._ui_dir.exists():
            app.router.add_get("/", self._handle_index)
            app.router.add_get("/{path:.*}", self._handle_static)

        web.run_app(app, host="0.0.0.0", port=self._port, print=None)

    async def _handle_index(self, request: Any) -> Any:
        from aiohttp import web
        return web.FileResponse(self._ui_dir / "index.html")

    async def _handle_static(self, request: Any) -> Any:
        from aiohttp import web
        path = request.match_info.get("path", "")
        file_path = self._ui_dir / path
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(self._ui_dir.resolve())):
                return web.Response(status=403, text="Forbidden")
        except (ValueError, OSError):
            return web.Response(status=404, text="Not Found")
        if file_path.exists() and file_path.is_file():
            return web.FileResponse(file_path)
        index_path = self._ui_dir / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(status=404, text="Not Found")

    async def _handle_status(self, request: Any) -> Any:
        from aiohttp import web
        status = self.read_status()
        if status is None:
            return web.json_response({"error": "No status available"}, status=503)
        return web.json_response(status)

    async def _handle_command(self, request: Any) -> Any:
        from aiohttp import web
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

    async def _handle_websocket(self, request: Any) -> Any:
        from aiohttp import web
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        try:
            while not ws.closed:
                status = self.read_status()
                if status:
                    await ws.send_json(status)
                import asyncio
                await asyncio.sleep(2)
        except Exception:
            pass
        finally:
            await ws.close()
        return ws


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP Proxy UI Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--status-path", required=True)
    parser.add_argument("--ui-dir", default=None)
    parser.add_argument("--command-path", default=None)
    args = parser.parse_args()

    server = UIServer(
        status_path=args.status_path,
        port=args.port,
        ui_dir=args.ui_dir,
        command_path=args.command_path,
    )
    server.run()
