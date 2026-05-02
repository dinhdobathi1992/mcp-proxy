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
    """Set up graceful shutdown on SIGTERM and SIGINT-style signals.

    SIGHUP is intentionally left to the lifecycle manager (which installs
    a config-reload handler once it has a manager to reload). Until then
    we register a temporary placeholder so an early SIGHUP does not kill
    the process with the default terminate disposition.
    """

    def _shutdown_handler(signum: int, frame: object) -> None:
        LOGGER.info("Received signal %s, shutting down...", signum)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)

    if hasattr(signal, "SIGHUP"):
        def _hup_placeholder(signum: int, frame: object) -> None:
            LOGGER.info("Received SIGHUP before manager ready; ignoring.")

        try:
            signal.signal(signal.SIGHUP, _hup_placeholder)
        except (ValueError, OSError):
            pass


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
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch config file for changes and hot-reload.",
    )
    parser.add_argument(
        "--health-interval",
        type=float,
        default=30.0,
        help="Health check interval in seconds.",
    )
    parser.add_argument(
        "--auth-api-key",
        default=None,
        help="API key for HTTP front authentication.",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=100,
        help="Requests per minute per IP (HTTP only).",
    )
    parser.add_argument(
        "--tls-cert",
        default=None,
        help="TLS certificate path for HTTPS.",
    )
    parser.add_argument(
        "--tls-key",
        default=None,
        help="TLS key path for HTTPS.",
    )
    parser.add_argument(
        "--log-format",
        choices=("text", "json"),
        default="text",
        help="Log format: text or json.",
    )
    parser.add_argument(
        "--ui-mode",
        choices=("off", "default", "advanced"),
        default="off",
        help="Management UI mode: off, default (read-only), or advanced (full admin).",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=8080,
        help="Management UI server port.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level, log_format=args.log_format)
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
            watch=args.watch,
            health_interval=args.health_interval,
            tls_cert=args.tls_cert,
            tls_key=args.tls_key,
            ui_mode=args.ui_mode,
            ui_port=args.ui_port,
            auth_api_key=args.auth_api_key,
            rate_limit=args.rate_limit,
        )
    except ConfigError as exc:
        LOGGER.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
