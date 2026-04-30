"""Minimal HTTP MCP fixture server for testing.

Usage:
    python tests/fixtures/backend_http.py [--port 9001]
"""

from __future__ import annotations

import argparse
import sys

from fastmcp import FastMCP

app = FastMCP(name="math-backend")


@app.tool()
def multiply(a: int, b: int) -> int:
    """Return the product of two integers."""
    return a * b


@app.tool()
def subtract(a: int, b: int) -> int:
    """Return a minus b."""
    return a - b


@app.prompt()
def math_intro() -> str:
    """Return an introductory math prompt."""
    return "This server provides basic math operations."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Math HTTP fixture backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    args = parser.parse_args()

    app.run(transport="http", host=args.host, port=args.port)
