#!/bin/sh
# Stop the Pi side: stream server, OpenAuto, FIFO writer.
# Run on the Pi: ~/auriga/scripts/pi-stop.sh
set -eu

if [ -f /tmp/auriga-stream.pid ]; then
  kill "$(cat /tmp/auriga-stream.pid)" 2>/dev/null || true
fi
pkill -f "[a]uriga_stream.py" 2>/dev/null || true

if [ -f /tmp/auriga-fifo-writer.pid ]; then
  kill "$(cat /tmp/auriga-fifo-writer.pid)" 2>/dev/null || true
fi

pkill -f "[/]build-openauto/bin/autoapp" 2>/dev/null || true
# autoapp normally runs as root.
sudo -n pkill -f "[/]build-openauto/bin/autoapp" 2>/dev/null || true

rm -f /tmp/auriga-in /tmp/auriga-autoapp.pid /tmp/auriga-stream.pid /tmp/auriga-fifo-writer.pid

echo "stopped autoapp, stream server and FIFO writer"
