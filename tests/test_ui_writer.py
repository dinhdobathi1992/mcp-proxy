from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mcp_proxy.ui_writer import StatusWriter


class TestStatusWriter:
    def test_write_creates_file(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        writer.write({
            "timestamp": "2026-05-01T18:00:00Z",
            "backends": [],
            "totals": {"requests": 0},
        })
        assert Path(path).exists()

    def test_write_produces_readable_format(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        data = {
            "timestamp": "2026-05-01T18:00:00Z",
            "backends": [{"name": "echo", "health": "healthy"}],
            "totals": {"requests": 42},
        }
        writer.write(data)

        raw = Path(path).read_bytes()
        size = struct.unpack("<I", raw[:4])[0]
        payload = raw[4 : 4 + size]
        parsed = json.loads(payload)
        assert parsed["backends"][0]["name"] == "echo"
        assert parsed["totals"]["requests"] == 42

    def test_write_overwrites_previous(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        writer.write({"v": 1})
        writer.write({"v": 2})

        raw = Path(path).read_bytes()
        size = struct.unpack("<I", raw[:4])[0]
        payload = raw[4 : 4 + size]
        assert json.loads(payload)["v"] == 2

    def test_write_empty_backends(self, tmp_path: Path):
        path = str(tmp_path / "status.dat")
        writer = StatusWriter(path)
        writer.write({"backends": [], "totals": {}})
        assert Path(path).stat().st_size > 0
