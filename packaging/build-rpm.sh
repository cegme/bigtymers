#!/bin/sh
# Builds dist/btyme-<version>-1.noarch.rpm. Needs rpmbuild (the rpm-build package).
# Usage: sh packaging/build-rpm.sh [version]
set -eu
cd "$(dirname "$0")/.."
VERSION="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)}"
TOP="$(mktemp -d)"
trap 'rm -rf "$TOP"' EXIT

mkdir -p "$TOP/SOURCES" "$TOP/SPECS" "$TOP/BUILD" "$TOP/RPMS" "$TOP/SRPMS"
cp bigtymers.py LICENSE "$TOP/SOURCES/"
cp packaging/btyme.spec "$TOP/SPECS/"
rpmbuild -bb --define "_topdir $TOP" --define "btyme_version $VERSION" "$TOP/SPECS/btyme.spec"
mkdir -p dist
cp "$TOP"/RPMS/noarch/*.rpm dist/
