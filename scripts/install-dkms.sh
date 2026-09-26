#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=$(tr -d "[:space:]" < "$ROOT/VERSION")
PACKAGE=faultsimdisk
SOURCE_DIR="/usr/src/${PACKAGE}-${VERSION}"

if (( EUID != 0 )); then
	echo "Run as root: sudo ./scripts/install-dkms.sh" >&2
	exit 1
fi

command -v dkms >/dev/null || {
	echo "Missing dkms. Install it with your distribution package manager." >&2
	exit 1
}

if dkms status -m "$PACKAGE" -v "$VERSION" 2>/dev/null | grep -q .; then
	echo "$PACKAGE/$VERSION is already registered with DKMS." >&2
	exit 1
fi

rm -rf "$SOURCE_DIR"
install -d "$SOURCE_DIR"
install -m 0644 "$ROOT/faultsimdisk.c" "$ROOT/Makefile" "$ROOT/dkms.conf" "$ROOT/VERSION" "$SOURCE_DIR/"

dkms add -m "$PACKAGE" -v "$VERSION"
dkms build -m "$PACKAGE" -v "$VERSION"
dkms install -m "$PACKAGE" -v "$VERSION"

echo "Installed $PACKAGE/$VERSION through DKMS."
echo "Load with: sudo modprobe faultsimdisk"
