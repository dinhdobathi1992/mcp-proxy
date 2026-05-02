from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .logging import get_logger

LOGGER = get_logger("ui_reader")


class CommandReader:
    """Reads commands from a JSONL file written by the UI.

    Drains the file by atomically renaming it to a sibling consume path before
    reading, so concurrent appenders never have their writes truncated. New
    writes after the rename land in a freshly-created file picked up on the
    next pass.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def read_commands(self) -> list[dict[str, Any]]:
        """Drain pending commands. Invalid lines are logged and skipped."""
        consume = self._path.with_suffix(self._path.suffix + ".consume")
        try:
            os.replace(self._path, consume)
        except FileNotFoundError:
            return []
        except OSError as exc:
            LOGGER.warning("Failed to rotate command file: %s", exc)
            return []

        try:
            text = consume.read_text(encoding="utf-8")
        except OSError as exc:
            LOGGER.warning("Failed to read command file: %s", exc)
            text = ""
        finally:
            try:
                consume.unlink()
            except OSError as exc:
                LOGGER.warning("Failed to remove consumed command file: %s", exc)

        commands: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                commands.append(json.loads(line))
            except json.JSONDecodeError as exc:
                LOGGER.warning("Skipping invalid command line: %s", exc)
        return commands
