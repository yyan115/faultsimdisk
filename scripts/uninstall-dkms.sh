#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=$(tr -d "[:space:]" < "$ROOT/VERSION")
PACKAGE=faultsimdisk
SOURCE_DIR="/usr/src/${PACKAGE}-${VERSION}"

if (( EUID != 0 )); then
	echo "Run as root: sudo ./scripts/uninstall-dkms.sh" >&2
	exit 1
fi

command -v dkms >/dev/null || { echo "Missing dkms." >&2; exit 1; }

dkms remove -m "$PACKAGE" -v "$VERSION" --all || true
rm -rf "$SOURCE_DIR"

echo "Removed $PACKAGE/$VERSION from DKMS."
