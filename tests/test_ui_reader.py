from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_proxy.ui_reader import CommandReader


class TestCommandReader:
    def test_read_empty_file(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        path.write_text("")
        reader = CommandReader(path)
        assert reader.read_commands() == []

    def test_read_single_command(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        cmd = {"id": "c1", "action": "disable_backend", "args": {"name": "echo"}}
        path.write_text(json.dumps(cmd) + "\n")
        reader = CommandReader(path)
        commands = reader.read_commands()
        assert len(commands) == 1
        assert commands[0]["action"] == "disable_backend"

    def test_read_multiple_commands(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        cmds = [
            {"id": "c1", "action": "disable_backend", "args": {"name": "echo"}},
            {"id": "c2", "action": "reload_config", "args": {}},
        ]
        path.write_text("\n".join(json.dumps(c) for c in cmds) + "\n")
        reader = CommandReader(path)
        commands = reader.read_commands()
        assert len(commands) == 2

    def test_read_clears_file(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        cmd = {"id": "c1", "action": "reload_config", "args": {}}
        path.write_text(json.dumps(cmd) + "\n")
        reader = CommandReader(path)
        reader.read_commands()
        assert path.read_text() == ""

    def test_read_skips_invalid_json(self, tmp_path: Path):
        path = tmp_path / "commands.jsonl"
        path.write_text("not json\n{\"id\":\"c1\",\"action\":\"reload_config\",\"args\":{}}\n")
        reader = CommandReader(path)
        commands = reader.read_commands()
        assert len(commands) == 1
        assert commands[0]["id"] == "c1"

    def test_read_nonexistent_file(self, tmp_path: Path):
        path = tmp_path / "nonexistent.jsonl"
        reader = CommandReader(path)
        assert reader.read_commands() == []
