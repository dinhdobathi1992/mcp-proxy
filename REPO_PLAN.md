# MCP Proxy Repo Plan

## Product Goal

Build a tiny Python MCP proxy that sits in front of multiple downstream MCP servers and exposes them as one MCP server. The proxy should stay intentionally thin: aggregate downstream tools, prompts, and resources without adding custom business logic in v1.

The implementation target is FastMCP 3.x using `create_proxy(...)` with the standard `mcpServers` config shape.

## Client Compatibility Requirements

The proxy must be planned to work cleanly with all of these clients:

- Claude Code
- Codex
- Cursor Agent / Cursor MCP
- OpenCode

### Compatibility Strategy

- Primary front transport: `stdio`
- Secondary front transport: `http`
- Primary install model: a stable executable on `PATH` named `mcp-proxy`
- Fallback install model: `python -m mcp_proxy.cli`

### Why `stdio` First

- Claude Code, Codex, Cursor, and OpenCode all support launching local MCP servers as a command plus args.
- `stdio` avoids remote auth, reverse proxying, and HTTP session edge cases.
- `stdio` is the lowest-friction path for local workflows and agent tooling.

### Host Requirements The Proxy Must Respect

- The process must be non-interactive.
- The process must be long-lived and stay attached to stdin/stdout until the host terminates it.
- The process must never print human-oriented logs to stdout.
- All logs must go to stderr.
- Startup must be deterministic and fast.
- The startup command must not require a shell wrapper such as `sh -lc`.
- Command plus args must be enough to launch the proxy in every target host.

### Engineering Targets

- Healthy local startup plus initial component discovery should complete in under 2 seconds.
- Worst-case healthy startup should stay under 5 seconds.
- The proxy must expose stable prefixed names such as `github_search_repos` and `jira_create_issue`.
- The proxy must preserve all three MCP component categories: tools, prompts, and resources.

Startup timing is an engineering target inferred from practical host expectations and documented MCP timeouts, not a hard limit from a single source.

## Client-Specific Expectations

### Claude Code

- Support project-scoped `.mcp.json` configuration.
- Support `command`, `args`, and `env`.
- Optimize for local `stdio` launch.
- Treat zero stdout noise as mandatory.

### Codex

- Support local `stdio` registration through `codex mcp add <name> -- <command> ...`.
- Support optional remote registration through `codex mcp add <name> --url <url>`.
- Keep the launch contract simple enough to map cleanly into Codex config and CLI flows.

### Cursor Agent

- Support `.cursor/mcp.json` with `mcpServers`.
- Optimize for local `stdio` launch.
- Keep the startup contract identical to Claude Code where possible.

### OpenCode

- Support local command-array based server launch.
- Support optional remote HTTP registration later.
- Avoid assumptions that require shell parsing.

## Core Design Constraints

- One front MCP server only.
- Multiple downstream MCP servers behind it.
- Use FastMCP `create_proxy(...)` as the primary aggregation mechanism.
- Use the standard `mcpServers` config shape for downstream definitions.
- Front server supports `stdio` and `http`.
- Downstream servers support `stdio` and `http`.
- Downstream `sse` may be allowed only as legacy compatibility, not as the preferred transport.
- Namespacing must be deterministic and collision-safe.
- v1 defaults to strict startup: bad config or missing local executables should fail fast.
- v1 uses fresh backend sessions per request.
- v1 does not implement custom routing, auth brokering, dynamic discovery, or hot reload.

## Repo Layout

```text
mcp-proxy/
  .gitignore
  README.md
  REPO_PLAN.md
  pyproject.toml
  servers.example.json
  docs/
    client-compatibility.md
  examples/
    claude-code.mcp.json
    cursor.mcp.json
    codex.config.toml
    opencode.jsonc
  src/
    mcp_proxy/
      __init__.py
      cli.py
      config.py
      logging.py
      server.py
      validate.py
  tests/
    conftest.py
    test_config.py
    test_proxy_smoke.py
    test_failures.py
    fixtures/
      backend_stdio.py
      backend_http.py
```

## File Responsibilities

- `README.md`: project overview, quickstart, and transport model.
- `REPO_PLAN.md`: implementation blueprint and acceptance criteria.
- `pyproject.toml`: package metadata, Python version, dependencies, and console script entrypoint.
- `servers.example.json`: canonical downstream config example using the `mcpServers` shape.
- `docs/client-compatibility.md`: host-specific integration notes and config examples for Claude Code, Codex, Cursor, and OpenCode.
- `examples/claude-code.mcp.json`: example Claude Code project config.
- `examples/cursor.mcp.json`: example Cursor project config.
- `examples/codex.config.toml`: example Codex config snippet.
- `examples/opencode.jsonc`: example OpenCode config snippet.
- `src/mcp_proxy/__init__.py`: package version.
- `src/mcp_proxy/cli.py`: CLI parsing, config validation mode, and server startup orchestration.
- `src/mcp_proxy/config.py`: load JSON config from disk and return a typed internal representation.
- `src/mcp_proxy/logging.py`: stderr-only logging setup.
- `src/mcp_proxy/server.py`: proxy builder and runtime wrapper around FastMCP.
- `src/mcp_proxy/validate.py`: structural validation and early startup checks.
- `tests/conftest.py`: shared fixtures and test helpers.
- `tests/test_config.py`: config and validation coverage.
- `tests/test_proxy_smoke.py`: healthy-path aggregation tests.
- `tests/test_failures.py`: startup and routing failure coverage.
- `tests/fixtures/backend_stdio.py`: toy local backend server.
- `tests/fixtures/backend_http.py`: toy remote backend server.

## Config Contract

Use the standard FastMCP-compatible `mcpServers` shape and do not invent a custom registry format in v1.

```json
{
  "mcpServers": {
    "echo": {
      "command": "python3",
      "args": ["tests/fixtures/backend_stdio.py"],
      "env": {}
    },
    "math": {
      "url": "http://127.0.0.1:9001/mcp",
      "transport": "http"
    }
  }
}
```

### Config Rules

- A backend is either command-based or URL-based, never both.
- Command-based backends default to `stdio`.
- URL-based backends default to `http`.
- `sse` is only accepted for downstream legacy compatibility.
- Unknown transport values fail validation.
- The proxy must preserve unrecognized backend fields so FastMCP can consume future-compatible options.

## Runtime Contract

- Front server defaults to `stdio`.
- Front `http` mode is supported for remote or shared deployments.
- Logging goes only to stderr.
- Validation errors return a non-zero exit status.
- `--check` mode validates config without starting the server.
- The proxy should be launchable by a single stable command on every target host.

## Milestones

### Milestone 1

Bootable scaffold with:

- package metadata
- console entrypoint
- config loader
- validation layer
- stderr logging
- `stdio` and `http` startup wiring
- `--check` mode
- client compatibility docs and host config examples

### Milestone 2

Functional mixed-backend aggregation:

- one local `stdio` fixture backend
- one remote `http` fixture backend
- proxy starts against both
- combined component listing is visible through the front server

### Milestone 3

Hardening and tests:

- config tests
- smoke routing tests
- failure-path tests
- strict-startup behavior
- timeout behavior
- duplicate-name collision coverage

### Milestone 4

Polish and delivery:

- refined README
- complete client setup examples
- install guidance for `pipx`, `uv tool`, or equivalent
- clear operational notes for local and remote deployments

## Implementation Order

1. Create `.gitignore`, `pyproject.toml`, and the `src/mcp_proxy/` package skeleton.
2. Create `servers.example.json` using the standard `mcpServers` format.
3. Implement `config.py`:
   - read JSON from disk
   - require top-level `mcpServers`
   - return a typed internal object
4. Implement `validate.py`:
   - ensure each backend is either command-based or URL-based
   - normalize transport defaults
   - reject invalid transport values
   - validate command and env types
   - validate HTTP URL shape
   - optionally fail fast for missing local executables
5. Implement `logging.py`:
   - stderr-only logging
   - stable log format
6. Implement `server.py`:
   - load and validate config
   - build the FastMCP proxy with `create_proxy(...)`
   - run in either `stdio` or `http`
7. Implement `cli.py`:
   - `--config`
   - `--transport`
   - `--host`
   - `--port`
   - `--name`
   - `--log-level`
   - `--check`
   - `--strict-startup`
8. Add compatibility docs and host-specific examples for Claude Code, Codex, Cursor, and OpenCode.
9. Add fixture servers and tests in later milestones.

## Definition of Done

- One command starts a front MCP proxy from a JSON config file.
- Another MCP host needs to connect to only that one front server.
- The front server exposes the union of downstream tools, prompts, and resources.
- Names are stable and collision-safe through deterministic prefixing.
- Claude Code can launch the proxy as a local stdio MCP server.
- Codex can register the proxy as a local stdio MCP server and optionally as remote HTTP later.
- Cursor can launch the proxy from `.cursor/mcp.json`.
- OpenCode can launch the proxy from a local command-array config.
- The proxy emits no human logs on stdout.
- Invalid startup conditions fail clearly and early.

## Deferred Work

- custom aliasing or nicer renamed tool surfaces
- dynamic backend discovery
- hot reload on config changes
- auth brokering for remote deployments
- per-backend health endpoints
- shared backend session optimization
