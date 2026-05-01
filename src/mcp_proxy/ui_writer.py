from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any


class StatusWriter:
    """Writes proxy status snapshot to a file for UI consumption."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def write(self, data: dict[str, Any]) -> None:
        """Write status snapshot atomically.

        Format: 4-byte little-endian size prefix + JSON payload.
        """
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        size = struct.pack("<I", len(payload))
        self._path.write_bytes(size + payload)
