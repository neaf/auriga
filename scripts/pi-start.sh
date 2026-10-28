#!/bin/sh
# Start the Pi side: OpenAuto capture + live WebSocket server.
# Run on the Pi from anywhere: ~/auriga/scripts/pi-start.sh
set -eu

BASE=${AURIGA_DIR:-$HOME/auriga}
RUN_DIR="$BASE/openauto-run"
STREAM_DIR="$BASE/stream"
LOG_DIR="$BASE/logs"
CAPTURE_DIR="$BASE/captures-openauto"
STAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$LOG_DIR" "$CAPTURE_DIR"

start_autoapp() {
  if pgrep -f "[/]build-openauto/bin/autoapp" >/dev/null 2>&1; then
    echo "autoapp already running (pid $(pgrep -f '[/]build-openauto/bin/autoapp' | head -n1))"
    return
  fi
  if [ ! -x "$RUN_DIR/run.sh" ]; then
    echo "missing $RUN_DIR/run.sh" >&2
    exit 1
  fi
  (
    cd "$RUN_DIR"
    nohup ./run.sh > "$LOG_DIR/openauto-$STAMP.log" 2>&1 &
    echo $! > /tmp/auriga-autoapp.pid
  )
  echo "autoapp started, log $LOG_DIR/openauto-$STAMP.log"
}

start_stream() {
  if pgrep -f "[a]uriga_stream.py" >/dev/null 2>&1; then
    echo "stream server already running (pid $(pgrep -f '[a]uriga_stream.py' | head -n1))"
    return
  fi
  if [ ! -f "$STREAM_DIR/auriga_stream.py" ]; then
    echo "missing $STREAM_DIR/auriga_stream.py" >&2
    exit 1
  fi
  (
    cd "$STREAM_DIR"
    nohup python3 auriga_stream.py > "$LOG_DIR/stream-$STAMP.log" 2>&1 &
    echo $! > /tmp/auriga-stream.pid
  )
  echo "stream server started, log $LOG_DIR/stream-$STAMP.log"
}

start_autoapp
sleep 1
start_stream

echo
echo "Pi side up."
echo "  autoapp: $(pgrep -f '[/]build-openauto/bin/autoapp' | head -n1 || echo stopped)"
echo "  stream:  $(pgrep -f '[a]uriga_stream.py' | head -n1 || echo stopped)"
echo "  capture: $CAPTURE_DIR"
echo "  logs:    $LOG_DIR"
echo
echo "On the Mac: scripts/mac-start.sh"
