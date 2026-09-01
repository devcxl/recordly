#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/devcxl/cabbage.git"
INSTALL_DIR="${CABBAGE_INSTALL_DIR:-$HOME/.local/share/cabbage}"
BIN_DIR="${CABBAGE_BIN_DIR:-$HOME/.local/bin}"
BIN_PATH="$BIN_DIR/cabbage"

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling Cabbage..."
  rm -rf "$INSTALL_DIR"
  rm -f "$BIN_PATH"
  echo "Cabbage uninstalled successfully."
  exit 0
fi

echo "==> Installing Cabbage CLI..."

# Check Python version
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: Python 3 is required but not installed." >&2
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
  echo "Error: Python 3.10 or higher is required (found $PY_VER)." >&2
  exit 1
fi

# Detect source directory
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

CLEANUP_TMP=0
TMP_DIR=""

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/../pyproject.toml" ] && [ -d "$SCRIPT_DIR/../cabbage_cli" ]; then
  SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
  echo "==> Installing from local source: $SOURCE_DIR"
else
  TMP_DIR="$(mktemp -d)"
  CLEANUP_TMP=1
  echo "==> Downloading latest release from $REPO_URL..."
  git clone --depth 1 "$REPO_URL" "$TMP_DIR"
  SOURCE_DIR="$TMP_DIR"
fi

cleanup() {
  if [ "$CLEANUP_TMP" -eq 1 ] && [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

# Prepare installation directory
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

echo "==> Creating dedicated virtual environment at $INSTALL_DIR/venv..."
python3 -m venv "$INSTALL_DIR/venv"

echo "==> Installing dependencies and cabbage CLI..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade --quiet pip setuptools wheel
"$INSTALL_DIR/venv/bin/pip" install --quiet "$SOURCE_DIR"

# Create entrypoint wrapper
cat > "$BIN_PATH" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/venv/bin/cabbage" "\$@"
EOF
chmod +x "$BIN_PATH"

echo "==> Successfully installed Cabbage to $BIN_PATH"

# PATH warning if needed
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo ""
  echo "Note: $BIN_DIR is not in your PATH."
  echo "Add the following line to your ~/.bashrc or ~/.zshrc:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "Verify installation with:"
echo "  cabbage --version"
