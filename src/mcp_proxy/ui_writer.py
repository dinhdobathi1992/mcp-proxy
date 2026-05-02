from __future__ import annotations

import json
import os
import struct
import tempfile
import threading
from pathlib import Path
from typing import Any


class StatusWriter:
    """Writes proxy status snapshot to a file for UI consumption.

    Each ``write`` produces the file atomically by writing to a sibling temp
    file and renaming, so readers never observe a torn payload.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def write(self, data: dict[str, Any]) -> None:
        """Write status snapshot atomically (size prefix + JSON payload)."""
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        size = struct.pack("<I", len(payload))

        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            fd, tmp_name = tempfile.mkstemp(
                prefix=self._path.name + ".",
                suffix=".tmp",
                dir=str(parent),
            )
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(size)
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_name, self._path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
