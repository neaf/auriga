#!/bin/sh
# Run the macOS capture build of OpenAuto from this directory.
#
# Start it through ../scripts/auriga.sh start: that script resolves
# AURIGA_CAPTURE_DIR and AURIGA_INPUT_FIFO once, creates the FIFO and its
# writer, and exports both. This wrapper has no defaults of its own, so the
# path autoapp reads and the path the stream server writes cannot diverge.
# Run from openauto-config so autoapp picks up openauto.ini/openauto-logs.ini.
# No sudo: macOS libusb can claim the dongle as the user.

set -eu
cd "$(dirname "$0")"

ROOT=$(cd .. && pwd)
if [ -z "${AURIGA_CAPTURE_DIR:-}" ] || [ -z "${AURIGA_INPUT_FIFO:-}" ]; then
  echo "run.sh: start through scripts/auriga.sh (it sets AURIGA_CAPTURE_DIR and AURIGA_INPUT_FIFO)" >&2
  exit 1
fi

BIN="$ROOT/build-openauto-mac/bin/autoapp"
if [ ! -x "$BIN" ]; then
  BIN=$(ls -1t "$ROOT"/build-openauto-mac/bin/autoapp-* 2>/dev/null | head -n 1 || true)
fi
if [ -z "${BIN:-}" ] || [ ! -x "$BIN" ]; then
  echo "autoapp binary not found under build-openauto-mac/bin (see docs/Build.md)" >&2
  exit 1
fi

mkdir -p "$AURIGA_CAPTURE_DIR"

echo "running $BIN"
echo "capture dir: $AURIGA_CAPTURE_DIR"
echo "input fifo: $AURIGA_INPUT_FIFO (echo 'tap 640 360' > $AURIGA_INPUT_FIFO)"

exec env \
  AURIGA_CAPTURE_DIR="$AURIGA_CAPTURE_DIR" \
  QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
  "$BIN" < "$AURIGA_INPUT_FIFO"
