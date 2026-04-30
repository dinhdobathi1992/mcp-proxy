"""Shared test fixtures for mcp-proxy tests."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import socket
from pathlib import Path
from typing import Generator

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
BACKEND_STDIO = FIXTURES_DIR / "backend_stdio.py"
BACKEND_HTTP = FIXTURES_DIR / "backend_http.py"


def _free_port() -> int:
    """Return an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def python_exe() -> str:
    """Return the current Python executable path."""
    return sys.executable


@pytest.fixture(scope="session")
def backend_stdio_path() -> Path:
    """Path to the stdio fixture backend script."""
    assert BACKEND_STDIO.exists(), f"Missing fixture: {BACKEND_STDIO}"
    return BACKEND_STDIO


@pytest.fixture(scope="session")
def backend_http_path() -> Path:
    """Path to the HTTP fixture backend script."""
    assert BACKEND_HTTP.exists(), f"Missing fixture: {BACKEND_HTTP}"
    return BACKEND_HTTP


@pytest.fixture(scope="session")
def http_backend_port() -> int:
    """Fixed free port for the HTTP fixture backend (allocated once per session)."""
    return _free_port()


@pytest.fixture(scope="session")
def http_backend_proc(
    python_exe: str,
    backend_http_path: Path,
    http_backend_port: int,
) -> Generator[subprocess.Popen, None, None]:
    """Start the HTTP fixture backend once for the entire test session."""
    proc = subprocess.Popen(
        [python_exe, str(backend_http_path), "--port", str(http_backend_port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for the server to accept connections.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", http_backend_port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail(f"HTTP backend did not start on port {http_backend_port} within 5s")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def make_config_file(tmp_path: Path):
    """Factory fixture: write a dict as JSON to a temp file and return the path."""

    def _make(data: dict) -> Path:
        p = tmp_path / "servers.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    return _make


@pytest.fixture
def stdio_config(
    python_exe: str,
    backend_stdio_path: Path,
    make_config_file,
) -> Path:
    """Write a valid stdio-only proxy config and return the path."""
    return make_config_file(
        {
            "mcpServers": {
                "echo": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                }
            }
        }
    )


@pytest.fixture
def mixed_config(
    python_exe: str,
    backend_stdio_path: Path,
    http_backend_port: int,
    http_backend_proc,
    make_config_file,
) -> Path:
    """Write a proxy config with stdio + http backends and return the path."""
    return make_config_file(
        {
            "mcpServers": {
                "echo": {
                    "command": python_exe,
                    "args": [str(backend_stdio_path)],
                },
                "math": {
                    "url": f"http://127.0.0.1:{http_backend_port}/mcp",
                },
            }
        }
    )
