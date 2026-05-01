from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

LOGGER_NAME = "mcp_proxy"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line with structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("backend", "duration_ms", "request_id"):
            val = getattr(record, key, None)
            if val is not None:
                data[key] = val
        return json.dumps(data, default=str)


def configure_logging(
    level: str = DEFAULT_LOG_LEVEL, log_format: str = "text"
) -> logging.Logger:
    """Configure stderr-only logging for MCP-safe process startup.

    Args:
        level: Log level name (e.g. "INFO", "WARNING").
        log_format: ``"text"`` for plain text, ``"json"`` for structured JSON.

    Logs must go to stderr so that stdout stays clean for MCP protocol
    communication when the proxy runs in stdio mode.
    """
    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    return logging.getLogger(LOGGER_NAME)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a package logger."""

    base_name = LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}"
    return logging.getLogger(base_name)
