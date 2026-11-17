#!/bin/sh
# Builds dist/btyme_<version>_all.deb. Needs dpkg-deb (Debian, Ubuntu or the dpkg package).
# Usage: sh packaging/build-deb.sh [version]
set -eu
cd "$(dirname "$0")/.."
VERSION="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

install -D -m 0755 bigtymers.py "$ROOT/usr/bin/btyme"
install -D -m 0644 LICENSE "$ROOT/usr/share/doc/btyme/copyright"
mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: btyme
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), tzdata
Maintainer: Christan Grant <cegme@users.noreply.github.com>
Homepage: https://ceg.me/bigtymers
Description: full screen analog and digital clock and countdown timer
 BigTymers shows the current time or the time left in a countdown timer
 in the terminal, with analog and digital faces, time zones and a
 flashing alarm. Made for exams and presentations.
CONTROL

mkdir -p dist
dpkg-deb --root-owner-group --build "$ROOT" "dist/btyme_${VERSION}_all.deb"
