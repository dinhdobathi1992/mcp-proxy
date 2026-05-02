from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from mcp_proxy.logging import configure_logging, get_logger


class TestStructuredLogging:
    def test_text_format_default(self, capsys):
        configure_logging("INFO", log_format="text")
        logger = get_logger("test")
        logger.info("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.err

    def test_json_format_produces_valid_json(self, capsys):
        configure_logging("INFO", log_format="json")
        logger = get_logger("test")
        logger.info("test message")
        captured = capsys.readouterr()
        lines = [l for l in captured.err.strip().split("\n") if l.strip()]
        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["level"] == "INFO"
        assert data["logger"] == "mcp_proxy.test"
        assert data["message"] == "test message"
        assert "timestamp" in data

    def test_json_format_includes_extra_fields(self, capsys):
        configure_logging("INFO", log_format="json")
        logger = get_logger("test")
        logger.info("with extra", extra={"backend": "echo", "duration_ms": 42})
        captured = capsys.readouterr()
        lines = [l for l in captured.err.strip().split("\n") if l.strip()]
        data = json.loads(lines[-1])
        assert data["backend"] == "echo"
        assert data["duration_ms"] == 42

    def test_log_level_filtering(self, capsys):
        configure_logging("WARNING", log_format="text")
        logger = get_logger("test")
        logger.info("should not appear")
        logger.warning("should appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.err
        assert "should appear" in captured.err
