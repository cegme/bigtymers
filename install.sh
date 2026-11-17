#!/bin/sh
# Installs the btyme command.
#   curl -fsSL https://ceg.me/bigtymers/install.sh | sh
# Remove it again with:
#   curl -fsSL https://ceg.me/bigtymers/install.sh | sh -s -- --uninstall
# Set BTYME_DIR to install somewhere other than ~/.local/bin.
set -eu

URL="https://ceg.me/bigtymers/bigtymers.py"
DIR="${BTYME_DIR:-$HOME/.local/bin}"
TARGET="$DIR/btyme"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$TARGET"
  echo "Removed $TARGET"
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "btyme needs Python 3.9 or newer, and python3 was not found." >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
  echo "btyme needs Python 3.9 or newer." >&2
  exit 1
fi

mkdir -p "$DIR"
TMP="$(mktemp "$DIR/.btyme.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$TMP"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$TMP" "$URL"
else
  echo "Install curl or wget and run this again." >&2
  exit 1
fi
chmod +x "$TMP"
mv "$TMP" "$TARGET"
trap - EXIT
echo "Installed $TARGET"

case ":$PATH:" in
  *":$DIR:"*) echo "Run: btyme 45m" ;;
  *) echo "Add $DIR to your PATH, for example:"
     echo "  echo 'export PATH=\"$DIR:\$PATH\"' >> ~/.profile"
     echo "Then run: btyme 45m" ;;
esac
