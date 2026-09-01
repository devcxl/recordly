#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-0.1.0}"
VERSION="${VERSION#v}"

DIST_DIR="$ROOT/dist"
BUILD_DIR="$(mktemp -d)"
PKG_ROOT="$BUILD_DIR/cabbage_${VERSION}_all"

cleanup() {
  rm -rf "$BUILD_DIR"
}
trap cleanup EXIT

echo "==> Building Debian package for cabbage v${VERSION}..."

mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/lib/python3/dist-packages/cabbage_cli"
mkdir -p "$DIST_DIR"

# Copy python package without caches
cp -r "$ROOT/cabbage_cli/"* "$PKG_ROOT/usr/lib/python3/dist-packages/cabbage_cli/"
find "$PKG_ROOT/usr/lib/python3/dist-packages/cabbage_cli" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PKG_ROOT/usr/lib/python3/dist-packages/cabbage_cli" -name "*.pyc" -delete 2>/dev/null || true

# Create /usr/bin/cabbage executable wrapper
cat > "$PKG_ROOT/usr/bin/cabbage" <<'EOF'
#!/usr/bin/env bash
exec python3 -m cabbage_cli "$@"
EOF
chmod 755 "$PKG_ROOT/usr/bin/cabbage"

# Create DEBIAN/control
cat > "$PKG_ROOT/DEBIAN/control" <<EOF
Package: cabbage
Version: ${VERSION}
Section: devel
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-yaml (>= 6.0)
Maintainer: devcxl <https://github.com/devcxl/cabbage>
Description: Spec-driven documentation management skill & CLI for software teams and AI agents.
 Cabbage enforces documentation lifecycles, structured requirement scenarios,
 impact analysis, signature verification, and CI gates for software teams and AI agents.
EOF

# Build .deb package
OUTPUT_DEB="$DIST_DIR/cabbage_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUTPUT_DEB"

echo "==> Successfully created Debian package: $OUTPUT_DEB"
