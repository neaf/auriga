#!/bin/sh
# Run the local macOS head unit (OpenAuto capture build) from this directory.
# Run it from openauto-config so autoapp picks up openauto.ini/openauto-logs.ini.
# No sudo by default: macOS libusb can claim the dongle as the user. If AOA
# control transfers fail with permissions, run this script via sudo.
set -eu
cd "$(dirname "$0")"

ROOT=$(cd .. && pwd)
BIN="$ROOT/build-openauto-mac/bin/autoapp"
if [ ! -x "$BIN" ]; then
  BIN=$(ls -1t "$ROOT"/build-openauto-mac/bin/autoapp-* 2>/dev/null | head -n1 || true)
fi
if [ -z "${BIN:-}" ] || [ ! -x "$BIN" ]; then
  echo "autoapp binary not found under build-openauto-mac/bin (see MAC-PORT.md)" >&2
  exit 1
fi

CAPTURE_DIR=${AURIGA_CAPTURE_DIR:-$ROOT/captures-mac}
mkdir -p "$CAPTURE_DIR"

FIFO=${AURIGA_INPUT_FIFO:-/tmp/auriga-in}
rm -f "$FIFO"
mkfifo "$FIFO"
# Keep a writer attached so autoapp's stdin open does not block.
sleep 86400 > "$FIFO" &
echo $! > /tmp/auriga-fifo-writer.pid

echo "running $BIN"
echo "capture dir: $CAPTURE_DIR"
echo "input fifo: $FIFO (echo 'tap 640 360' > $FIFO)"

exec env \
  AURIGA_CAPTURE_DIR="$CAPTURE_DIR" \
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
  "$BIN" < "$FIFO"
