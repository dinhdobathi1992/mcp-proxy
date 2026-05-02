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
    """Configure stderr-only logging for the ``mcp_proxy`` package.

    Configures only the package logger (not the root logger) so embedders
    that already set up their own logging are not disturbed. Logs go to
    stderr to keep stdout clean for MCP stdio transport.
    """
    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    package_logger = logging.getLogger(LOGGER_NAME)
    package_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    for existing in list(package_logger.handlers):
        package_logger.removeHandler(existing)
    package_logger.addHandler(handler)
    package_logger.propagate = False

    return package_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a package logger."""

    base_name = LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}"
    return logging.getLogger(base_name)
