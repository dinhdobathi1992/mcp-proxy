"""Minimal stdio MCP fixture server for testing."""

from __future__ import annotations

import sys

from fastmcp import FastMCP

app = FastMCP(name="echo-backend")


@app.tool()
def echo(message: str) -> str:
    """Return the message unchanged."""
    return message


@app.tool()
def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


@app.prompt()
def greet(name: str) -> str:
    """Generate a greeting prompt."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    app.run(transport="stdio")
