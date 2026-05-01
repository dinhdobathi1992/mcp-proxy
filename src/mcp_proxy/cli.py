from __future__ import annotations

import argparse
import signal
from pathlib import Path
from typing import Sequence

from .config import load_config
from .logging import configure_logging, get_logger
from .server import run_proxy
from .validate import ConfigError

LOGGER = get_logger("cli")


def _setup_signal_handlers() -> None:
    """Set up graceful shutdown on SIGTERM."""

    def _handler(signum: int, frame: object) -> None:
        LOGGER.info("Received signal %s, shutting down...", signum)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handler)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the proxy process."""

    parser = argparse.ArgumentParser(
        prog="mcp-proxy",
        description="Run a thin FastMCP proxy in front of multiple downstream MCP servers.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("servers.json"),
        help="Path to the downstream server config JSON file.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="Front transport to expose to the MCP host.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host when using --transport http.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port when using --transport http.",
    )
    parser.add_argument(
        "--name",
        default="mcp-proxy",
        help="Name reported by the front MCP server.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level sent to stderr.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate config and exit without starting the server.",
    )
    parser.add_argument(
        "--strict-startup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail fast for startup checks such as missing local executables.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    _setup_signal_handlers()

    try:
        if args.check:
            config = load_config(args.config, strict_startup=args.strict_startup)
            LOGGER.info(
                "Validated config %s with %d active backend(s), %d disabled.",
                config.path,
                len(config.backends),
                len(config.disabled_backends),
            )
            return 0

        return run_proxy(
            args.config,
            transport=args.transport,
            host=args.host,
            port=args.port,
            name=args.name,
            strict_startup=args.strict_startup,
        )
    except ConfigError as exc:
        LOGGER.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
