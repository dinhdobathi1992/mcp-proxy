from __future__ import annotations

import logging
import sys

LOGGER_NAME = "mcp_proxy"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = DEFAULT_LOG_LEVEL) -> logging.Logger:
    """Configure stderr-only logging for MCP-safe process startup."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=DEFAULT_LOG_FORMAT,
        stream=sys.stderr,
        force=True,
    )
    return logging.getLogger(LOGGER_NAME)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a package logger."""

    base_name = LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}"
    return logging.getLogger(base_name)
