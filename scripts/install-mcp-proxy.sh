#!/usr/bin/env bash
# install-mcp-proxy.sh
#
# Register mcp-proxy into one or more AI agent configs.
#
# Usage:
#   ./scripts/install-mcp-proxy.sh [--claude] [--cursor] [--codex] [--opencode] [--all]
#
# Options:
#   --claude    Inject into ~/.claude/mcp.json
#   --cursor    Inject into ~/.cursor/mcp.json
#   --codex     Inject into ~/.codex/config.toml
#   --opencode  Inject into ~/.config/opencode/opencode.json
#   --all       Inject into all of the above
#   --dry-run   Print what would change without writing
#   --remove    Remove the mcp-proxy entry instead of adding it
#
# The script is idempotent: running it twice does not duplicate entries.

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolved paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROXY_BIN="${PROXY_ROOT}/.venv/bin/mcp-proxy"
SERVERS_JSON="${PROXY_ROOT}/servers.json"
ENTRY_NAME="mcp-proxy"

CLAUDE_MCP="${HOME}/.claude/mcp.json"
CURSOR_MCP="${HOME}/.cursor/mcp.json"
CODEX_TOML="${HOME}/.codex/config.toml"
OPENCODE_JSON="${HOME}/.config/opencode/opencode.json"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
DO_CLAUDE=0
DO_CURSOR=0
DO_CODEX=0
DO_OPENCODE=0
DRY_RUN=0
REMOVE=0

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 [--claude] [--cursor] [--codex] [--opencode] [--all] [--dry-run] [--remove]"
    exit 1
fi

for arg in "$@"; do
    case "$arg" in
        --claude)   DO_CLAUDE=1 ;;
        --cursor)   DO_CURSOR=1 ;;
        --codex)    DO_CODEX=1 ;;
        --opencode) DO_OPENCODE=1 ;;
        --all)      DO_CLAUDE=1; DO_CURSOR=1; DO_CODEX=1; DO_OPENCODE=1 ;;
        --dry-run)  DRY_RUN=1 ;;
        --remove)   REMOVE=1 ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "  $*"; }
ok()   { echo "  ✓ $*"; }
skip() { echo "  - $*"; }
warn() { echo "  ! $*"; }

write_file() {
    local path="$1"
    local content="$2"
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "    [dry-run] would write: ${path}"
    else
        mkdir -p "$(dirname "$path")"
        printf '%s\n' "$content" > "$path"
    fi
}

backup_file() {
    local path="$1"
    if [[ -f "$path" && $DRY_RUN -eq 0 ]]; then
        cp "$path" "${path}.bak-$(date +%Y%m%d_%H%M%S)"
    fi
}

require_python() {
    if ! command -v python3 &>/dev/null; then
        echo "python3 is required but not found on PATH"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
echo ""
echo "mcp-proxy installer"
echo "-------------------"
echo "  proxy bin  : ${PROXY_BIN}"
echo "  servers.json: ${SERVERS_JSON}"
echo ""

if [[ ! -f "$PROXY_BIN" ]]; then
    warn "Proxy binary not found: ${PROXY_BIN}"
    warn "Run 'uv sync' inside ${PROXY_ROOT} first."
    exit 1
fi

if [[ ! -f "$SERVERS_JSON" ]]; then
    warn "servers.json not found: ${SERVERS_JSON}"
    warn "Create it with at least one backend before installing."
    exit 1
fi

# ---------------------------------------------------------------------------
# JSON helpers (pure python3, no jq dependency)
# ---------------------------------------------------------------------------
json_has_key() {
    # json_has_key <file> <key_path>  e.g. json_has_key file.json mcpServers.proxy
    python3 - "$1" "$2" <<'EOF'
import json, sys
path = sys.argv[2].split(".")
try:
    d = json.load(open(sys.argv[1]))
    for key in path:
        d = d[key]
    sys.exit(0)
except (KeyError, TypeError, FileNotFoundError):
    sys.exit(1)
EOF
}

json_set_mcp_entry() {
    # Upsert mcpServers.<name> in a JSON file.
    python3 - "$1" "$2" "$3" "$4" <<'EOF'
import json, sys

file_path  = sys.argv[1]
entry_name = sys.argv[2]
proxy_bin  = sys.argv[3]
servers_json = sys.argv[4]

try:
    with open(file_path) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}

data.setdefault("mcpServers", {})
data["mcpServers"][entry_name] = {
    "command": proxy_bin,
    "args": ["--config", servers_json]
}

with open(file_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(json.dumps(data["mcpServers"][entry_name], indent=2))
EOF
}

json_remove_mcp_entry() {
    python3 - "$1" "$2" <<'EOF'
import json, sys

file_path  = sys.argv[1]
entry_name = sys.argv[2]

try:
    with open(file_path) as f:
        data = json.load(f)
except FileNotFoundError:
    sys.exit(0)

removed = data.get("mcpServers", {}).pop(entry_name, None)
if removed:
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"removed '{entry_name}'")
else:
    print(f"'{entry_name}' was not present")
EOF
}

json_set_opencode_entry() {
    python3 - "$1" "$2" "$3" <<'EOF'
import json, sys

file_path    = sys.argv[1]
proxy_bin    = sys.argv[2]
servers_json = sys.argv[3]

try:
    with open(file_path) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}

data.setdefault("mcp", {})
data["mcp"]["mcp-proxy"] = {
    "type": "local",
    "command": [proxy_bin, "--config", servers_json],
    "enabled": True
}

with open(file_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(json.dumps(data["mcp"]["mcp-proxy"], indent=2))
EOF
}

json_remove_opencode_entry() {
    python3 - "$1" <<'EOF'
import json, sys

file_path = sys.argv[1]

try:
    with open(file_path) as f:
        data = json.load(f)
except FileNotFoundError:
    sys.exit(0)

removed = data.get("mcp", {}).pop("mcp-proxy", None)
if removed:
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print("removed 'mcp-proxy'")
else:
    print("'mcp-proxy' was not present")
EOF
}

# ---------------------------------------------------------------------------
# Codex TOML helpers
# ---------------------------------------------------------------------------
toml_has_mcp_proxy() {
    grep -q '^\[mcp_servers\.mcp-proxy\]' "$1" 2>/dev/null
}

toml_add_mcp_proxy() {
    local file="$1"
    # Append the stanza; idempotency is checked before calling this.
    cat >> "$file" <<TOML

[mcp_servers.mcp-proxy]
command = "${PROXY_BIN}"
args = ["--config", "${SERVERS_JSON}"]
TOML
}

toml_remove_mcp_proxy() {
    local file="$1"
    # Remove the [mcp_servers.mcp-proxy] block (header + following non-header lines)
    python3 - "$file" <<'EOF'
import sys, re

path = sys.argv[1]
try:
    text = open(path).read()
except FileNotFoundError:
    sys.exit(0)

# Remove block starting at [mcp_servers.mcp-proxy] up to next [section] or EOF
cleaned = re.sub(
    r'\n\[mcp_servers\.mcp-proxy\][^\[]*',
    '',
    text,
    flags=re.DOTALL
)
open(path, "w").write(cleaned)
print("removed [mcp_servers.mcp-proxy] block")
EOF
}

# ---------------------------------------------------------------------------
# Install / Remove per client
# ---------------------------------------------------------------------------
install_json_client() {
    local label="$1"
    local file="$2"

    echo "[${label}] ${file}"

    if [[ $REMOVE -eq 1 ]]; then
        if [[ ! -f "$file" ]]; then
            skip "file not found, nothing to remove"
            return
        fi
        backup_file "$file"
        if [[ $DRY_RUN -eq 0 ]]; then
            result=$(json_remove_mcp_entry "$file" "$ENTRY_NAME")
            ok "$result"
        else
            echo "    [dry-run] would remove '${ENTRY_NAME}' from ${file}"
        fi
        return
    fi

    backup_file "$file"
    if [[ $DRY_RUN -eq 0 ]]; then
        result=$(json_set_mcp_entry "$file" "$ENTRY_NAME" "$PROXY_BIN" "$SERVERS_JSON")
        ok "wrote entry:"
        echo "$result" | sed 's/^/      /'
    else
        echo "    [dry-run] would upsert '${ENTRY_NAME}' in ${file}"
    fi
    echo ""
}

install_codex() {
    local file="$CODEX_TOML"
    echo "[codex] ${file}"

    if [[ $REMOVE -eq 1 ]]; then
        if [[ ! -f "$file" ]]; then
            skip "file not found, nothing to remove"
            return
        fi
        backup_file "$file"
        if [[ $DRY_RUN -eq 0 ]]; then
            result=$(toml_remove_mcp_proxy "$file")
            ok "$result"
        else
            echo "    [dry-run] would remove [mcp_servers.mcp-proxy] from ${file}"
        fi
        echo ""
        return
    fi

    if toml_has_mcp_proxy "$file"; then
        skip "entry already present, skipping (use --remove first to replace)"
        echo ""
        return
    fi

    backup_file "$file"
    if [[ $DRY_RUN -eq 0 ]]; then
        toml_add_mcp_proxy "$file"
        ok "appended [mcp_servers.mcp-proxy] block"
    else
        echo "    [dry-run] would append [mcp_servers.mcp-proxy] to ${file}"
    fi
    echo ""
}

install_opencode() {
    local file="$OPENCODE_JSON"
    echo "[opencode] ${file}"

    if [[ $REMOVE -eq 1 ]]; then
        if [[ ! -f "$file" ]]; then
            skip "file not found, nothing to remove"
            return
        fi
        backup_file "$file"
        if [[ $DRY_RUN -eq 0 ]]; then
            result=$(json_remove_opencode_entry "$file")
            ok "$result"
        else
            echo "    [dry-run] would remove mcp.mcp-proxy from ${file}"
        fi
        echo ""
        return
    fi

    backup_file "$file"
    if [[ $DRY_RUN -eq 0 ]]; then
        result=$(json_set_opencode_entry "$file" "$PROXY_BIN" "$SERVERS_JSON")
        ok "wrote entry:"
        echo "$result" | sed 's/^/      /'
    else
        echo "    [dry-run] would upsert mcp.mcp-proxy in ${file}"
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
require_python

[[ $DO_CLAUDE   -eq 1 ]] && install_json_client "claude"   "$CLAUDE_MCP"
[[ $DO_CURSOR   -eq 1 ]] && install_json_client "cursor"   "$CURSOR_MCP"
[[ $DO_CODEX    -eq 1 ]] && install_codex
[[ $DO_OPENCODE -eq 1 ]] && install_opencode

echo "Done."
echo ""
echo "Restart / reload each client to pick up the new MCP server."
