from __future__ import annotations

import asyncio
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
    ) -> None:
        self._status_path = Path(status_path)
        self._port = port
        self._ui_dir = Path(ui_dir) if ui_dir else None

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

    async def run(self) -> None:
        """Start the UI server."""
        try:
            from aiohttp import web
        except ImportError:
            LOGGER.error(
                "UI server requires 'aiohttp'. Install with: uv add aiohttp"
            )
            return

        app = web.Application()
        app.router.add_get("/api/status", self._handle_status)
        app.router.add_get("/ws", self._handle_websocket)
        if self._ui_dir and self._ui_dir.exists():
            app.router.add_static("/", self._ui_dir)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        LOGGER.info("UI server running on http://0.0.0.0:%s", self._port)

        # Keep running
        await asyncio.Event().wait()

    async def _handle_status(self, request: Any) -> Any:
        from aiohttp import web

        status = self.read_status()
        if status is None:
            return web.json_response({"error": "No status available"}, status=503)
        return web.json_response(status)

    async def _handle_websocket(self, request: Any) -> Any:
        from aiohttp import web

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        try:
            while not ws.closed:
                status = self.read_status()
                if status:
                    await ws.send_json(status)
                await asyncio.sleep(2)
        except Exception:
            pass
        finally:
            await ws.close()
        return ws
