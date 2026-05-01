from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .logging import get_logger

LOGGER = get_logger("ui_reader")


class CommandReader:
    """Reads commands from a JSONL file written by the UI."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def read_commands(self) -> list[dict[str, Any]]:
        """Read all commands and clear the file.

        Returns list of command dicts. Invalid lines are logged and skipped.
        """
        if not self._path.exists():
            return []

        try:
            text = self._path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            LOGGER.warning("Failed to read command file: %s", exc)
            return []

        if not text:
            return []

        commands: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                commands.append(json.loads(line))
            except json.JSONDecodeError as exc:
                LOGGER.warning("Skipping invalid command line: %s", exc)

        # Clear the file after reading
        try:
            self._path.write_text("", encoding="utf-8")
        except OSError as exc:
            LOGGER.warning("Failed to clear command file: %s", exc)

        return commands
