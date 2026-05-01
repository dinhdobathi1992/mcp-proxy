from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mcp_proxy.ui_server import UIServer


class TestUIServer:
    def test_read_status(self, tmp_path: Path):
        status_path = tmp_path / "status.dat"
        data = {"backends": [], "totals": {"requests": 0}}
        payload = json.dumps(data).encode()
        status_path.write_bytes(struct.pack("<I", len(payload)) + payload)

        server = UIServer(status_path=str(status_path), port=0)
        result = server.read_status()
        assert result["totals"]["requests"] == 0

    def test_read_status_missing_file(self, tmp_path: Path):
        server = UIServer(status_path=str(tmp_path / "nonexistent"), port=0)
        result = server.read_status()
        assert result is None
