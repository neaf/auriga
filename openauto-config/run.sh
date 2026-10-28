#!/bin/sh
set -eu
cd "$(dirname "$0")"

BIN=../build-openauto/bin/autoapp
if [ ! -x "$BIN" ]; then
  BIN=$(ls -1t ../build-openauto/bin/autoapp-* 2>/dev/null | head -n1)
fi
if [ -z "$BIN" ] || [ ! -x "$BIN" ]; then
  echo "autoapp binary not found under ../build-openauto/bin" >&2
  exit 1
fi

CAPTURE_DIR=${AURIGA_CAPTURE_DIR:-$(cd .. && pwd)/captures-openauto}
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

exec sudo env \
  AURIGA_CAPTURE_DIR="$CAPTURE_DIR" \
  QT_QPA_PLATFORM=offscreen \
  LD_LIBRARY_PATH=/home/pi/auriga/build-aasdk/lib \
  "$BIN" < "$FIFO"
