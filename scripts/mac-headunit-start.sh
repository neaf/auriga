#!/bin/sh
# Start the local macOS head unit: OpenAuto capture + WebSocket stream server.
# Dongle direct to the Mac; no Pi, no SSH tunnel.
# Run on the Mac: ./scripts/mac-headunit-start.sh
set -eu

BASE=${AURIGA_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
RUN_DIR="$BASE/openauto-config"
STREAM_DIR="$BASE/stream"
LOG_DIR="$BASE/logs"
CAPTURE_DIR=${AURIGA_CAPTURE_DIR:-$BASE/captures-mac}
STAMP=$(date +%Y%m%d-%H%M%S)
PY=${AURIGA_PYTHON:-$BASE/.venv/bin/python}

if [ ! -x "$PY" ]; then
  PY=$(command -v python3 || true)
fi
if [ -z "$PY" ]; then
  echo "python3 not found" >&2
  exit 1
fi
if ! "$PY" -c "import websockets" >/dev/null 2>&1; then
  echo "missing python websockets for $PY" >&2
  echo "create the venv: /opt/homebrew/bin/python3.14 -m venv .venv && .venv/bin/pip install websockets" >&2
  exit 1
fi

mkdir -p "$LOG_DIR" "$CAPTURE_DIR"

start_autoapp() {
  if pgrep -f "[b]uild-openauto-mac/bin/autoapp" >/dev/null 2>&1; then
    echo "autoapp already running (pid $(pgrep -f '[b]uild-openauto-mac/bin/autoapp' | head -n1))"
    return
  fi
  if [ ! -x "$RUN_DIR/run-mac.sh" ]; then
    echo "missing $RUN_DIR/run-mac.sh" >&2
    exit 1
  fi
  (
    cd "$RUN_DIR"
    nohup ./run-mac.sh > "$LOG_DIR/openauto-mac-$STAMP.log" 2>&1 &
    echo $! > /tmp/auriga-mac-autoapp.pid
  )
  echo "autoapp started, log $LOG_DIR/openauto-mac-$STAMP.log"
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
    nohup "$PY" auriga_stream.py \
      --capture-dir "$CAPTURE_DIR" \
      --fifo /tmp/auriga-in \
      > "$LOG_DIR/stream-mac-$STAMP.log" 2>&1 &
    echo $! > /tmp/auriga-mac-stream.pid
  )
  echo "stream server started, log $LOG_DIR/stream-mac-$STAMP.log"
}

start_autoapp
sleep 1
start_stream

# Keep the Mac awake while the head unit runs.
if ! pgrep -f "[c]affeinate -dimsu" >/dev/null 2>&1; then
  nohup caffeinate -dimsu >/dev/null 2>&1 &
  echo $! > /tmp/auriga-mac-caffeinate.pid
fi

echo
echo "Mac head unit up."
echo "  autoapp: $(pgrep -f '[b]uild-openauto-mac/bin/autoapp' | head -n1 || echo stopped)"
echo "  stream:  $(pgrep -f '[a]uriga_stream.py' | head -n1 || echo stopped)"
echo "  capture: $CAPTURE_DIR"
echo "  logs:    $LOG_DIR"
echo

if open -a "Brave Browser" "http://localhost:8080" 2>/dev/null; then
  echo "opened Brave at http://localhost:8080"
else
  open "http://localhost:8080"
  echo "opened default browser at http://localhost:8080"
fi
