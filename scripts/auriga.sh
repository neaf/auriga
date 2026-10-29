#!/bin/sh
# Auriga head unit control (macOS): start | stop | status.
#
# The only runtime entry point. It resolves the capture directory and the input
# FIFO once, exports both to the head unit (openauto-config/run.sh) and passes
# them to the stream server, owns the single-instance lock, and waits for the
# HTTP socket instead of sleeping. See docs/Android Auto head unit.md#runtime.

set -eu

BASE=${AURIGA_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
RUN_DIR=$BASE/openauto-config
STREAM_DIR=$BASE/stream
LOG_DIR=$BASE/logs
CAPTURE_DIR=${AURIGA_CAPTURE_DIR:-$BASE/captures-mac}
FIFO=${AURIGA_INPUT_FIFO:-/tmp/auriga-in}
PY=${AURIGA_PYTHON:-$BASE/.venv/bin/python}

LOCK=$CAPTURE_DIR/.auriga.lock
START_GUARD=$CAPTURE_DIR/.auriga.start
HTTP_PORT=8080
WS_PORT=8081
READY_TIMEOUT=${AURIGA_READY_TIMEOUT:-20}
STAMP=$(date +%Y%m%d-%H%M%S)
AUTOAPP_LOG=$LOG_DIR/openauto-mac-$STAMP.log
STREAM_LOG=$LOG_DIR/stream-mac-$STAMP.log

# Single source for both paths; run.sh refuses to guess rather than defaulting
# them a second time (a divergent default writes the FIFO where autoapp does not
# read it).
export AURIGA_CAPTURE_DIR="$CAPTURE_DIR"
export AURIGA_INPUT_FIFO="$FIFO"

AUTOAPP_MATCH='build-openauto-mac/bin/autoapp'
AUTOAPP_PGREP='[b]uild-openauto-mac/bin/autoapp'
STREAM_MATCH='auriga_stream.py'
STREAM_PGREP='[a]uriga_stream.py'

# One writer must stay attached to the FIFO: autoapp opens its stdin blocking,
# and EOF stops the input reader for the rest of the run. A day-long sleep
# silently disables touch after 24 h, so the writer sleeps a year.
FIFO_WRITER_SECONDS=31536000

say() { echo "auriga: $*"; }
die() { echo "auriga: $*" >&2; exit 1; }

alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
cmdline() { ps -p "$1" -o command= 2>/dev/null || true; }
port_open() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }
tail_log() { if [ -f "$1" ]; then tail -n 20 "$1" >&2; fi; }

# The lock file holds one "role pid" line per component of the running pair.
lock_pid() {
  [ -f "$LOCK" ] || return 0
  sed -n "s/^$1 //p" "$LOCK" 2>/dev/null | head -n 1
}

find_autoapp() {
  p=$(lock_pid autoapp)
  if [ -n "$p" ] && alive "$p"; then
    case "$(cmdline "$p")" in
      *"$AUTOAPP_MATCH"*) echo "$p"; return 0 ;;
    esac
  fi
  pgrep -f "$AUTOAPP_PGREP" 2>/dev/null | head -n 1 || true
}

find_stream() {
  p=$(lock_pid stream)
  if [ -n "$p" ] && alive "$p"; then
    case "$(cmdline "$p")" in
      *"$STREAM_MATCH"*) echo "$p"; return 0 ;;
    esac
  fi
  pgrep -f "$STREAM_PGREP" 2>/dev/null | head -n 1 || true
}

take_guard() {
  if [ -d "$START_GUARD" ]; then
    other=$(cat "$START_GUARD/pid" 2>/dev/null || true)
    if [ -n "$other" ] && alive "$other"; then
      die "another start is in progress (pid $other)"
    fi
    rm -rf "$START_GUARD"
  fi
  mkdir "$START_GUARD"
  echo $$ >"$START_GUARD/pid"
}

release_guard() { rm -rf "$START_GUARD"; }

kill_tree() {
  pid=${1:-}
  [ -n "$pid" ] || return 0
  pkill -P "$pid" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
}

wait_port() {
  port=$1
  n=$(( ${2:-20} * 4 ))
  while [ "$n" -gt 0 ]; do
    if port_open "$port"; then return 0; fi
    sleep 0.25
    n=$(( n - 1 ))
  done
  return 1
}

start_fifo() {
  rm -f "$FIFO"
  mkfifo "$FIFO"
  sleep "$FIFO_WRITER_SECONDS" >"$FIFO" 2>/dev/null &
  FIFO_PID=$!
}

start_autoapp() {
  [ -x "$RUN_DIR/run.sh" ] || die "missing $RUN_DIR/run.sh"
  ( cd "$RUN_DIR" && exec nohup ./run.sh >"$AUTOAPP_LOG" 2>&1 ) &
  AUTOAPP_PID=$!
}

start_stream() {
  [ -f "$STREAM_DIR/auriga_stream.py" ] || die "missing $STREAM_DIR/auriga_stream.py"
  ( cd "$STREAM_DIR" && exec nohup "$PY" auriga_stream.py \
      --capture-dir "$CAPTURE_DIR" --fifo "$FIFO" >"$STREAM_LOG" 2>&1 ) &
  STREAM_PID=$!
}

start_caffeinate() {
  CAFFEINATE_PID=
  if pgrep -f "[c]affeinate -dimsu" >/dev/null 2>&1; then return 0; fi
  nohup caffeinate -dimsu >/dev/null 2>&1 &
  CAFFEINATE_PID=$!
}

write_lock() {
  {
    echo "autoapp $AUTOAPP_PID"
    echo "stream $STREAM_PID"
    if [ -n "${FIFO_PID:-}" ]; then echo "fifo $FIFO_PID"; fi
    if [ -n "${CAFFEINATE_PID:-}" ]; then echo "caffeinate $CAFFEINATE_PID"; fi
  } >"$LOCK"
}

rollback_start() {
  tail_log "$STREAM_LOG"
  tail_log "$AUTOAPP_LOG"
  kill_tree "${AUTOAPP_PID:-}"
  kill_tree "${STREAM_PID:-}"
  kill_tree "${FIFO_PID:-}"
  rm -f "$FIFO"
  release_guard
}

print_summary() {
  echo
  echo "Auriga head unit up."
  echo "  autoapp: pid $AUTOAPP_PID, log $AUTOAPP_LOG"
  echo "  stream:  pid $STREAM_PID, log $STREAM_LOG"
  echo "  capture: $CAPTURE_DIR"
  echo "  fifo:    $FIFO"
  echo "  ui:      http://localhost:$HTTP_PORT"
  echo
}

open_browser() {
  if open -a "Brave Browser" "http://localhost:$HTTP_PORT" 2>/dev/null; then
    say "opened Brave at http://localhost:$HTTP_PORT"
  else
    open "http://localhost:$HTTP_PORT" 2>/dev/null || true
    say "opened the default browser at http://localhost:$HTTP_PORT"
  fi
}

cmd_start() {
  [ "$(uname -s)" = Darwin ] || die "macOS only (docs/Build.md)"
  mkdir -p "$LOG_DIR" "$CAPTURE_DIR"
  take_guard
  trap 'release_guard' EXIT

  p=$(find_autoapp)
  s=$(find_stream)
  if [ -n "$p" ] || [ -n "$s" ]; then
    say "already running (autoapp ${p:-none}, stream ${s:-none}); refusing a second pair"
    cmd_status || true
    release_guard
    return 0
  fi
  rm -f "$LOCK"

  if port_open "$HTTP_PORT"; then die "127.0.0.1:$HTTP_PORT is already in use"; fi
  if port_open "$WS_PORT"; then die "127.0.0.1:$WS_PORT is already in use"; fi

  if [ ! -x "$PY" ]; then PY=$(command -v python3 || true); fi
  [ -n "$PY" ] || die "python3 not found"
  if ! "$PY" -c "import websockets" >/dev/null 2>&1; then
    die "missing python websockets for $PY (create .venv: see docs/Build.md)"
  fi

  start_fifo
  start_autoapp
  start_stream

  if ! wait_port "$HTTP_PORT" "$READY_TIMEOUT"; then
    echo "auriga: stream server did not listen on 127.0.0.1:$HTTP_PORT within ${READY_TIMEOUT}s" >&2
    rollback_start
    exit 1
  fi
  if ! alive "$STREAM_PID"; then
    echo "auriga: stream server exited during startup" >&2
    rollback_start
    exit 1
  fi
  if ! alive "$AUTOAPP_PID"; then
    echo "auriga: autoapp exited during startup" >&2
    rollback_start
    exit 1
  fi

  start_caffeinate
  write_lock
  print_summary
  open_browser
  release_guard
}

# Signal one component. The cmdline check keeps a recycled pid from being killed.
stop_pid() {
  pid=${1:-}
  match=${2:-}
  grace=${3:-10}
  [ -n "$pid" ] || return 0
  alive "$pid" || return 0
  if [ -n "$match" ]; then
    case "$(cmdline "$pid")" in
      *"$match"*) ;;
      *) say "skip pid $pid (not a $match process)" >&2; return 0 ;;
    esac
  fi
  kill "$pid" 2>/dev/null || true
  n=$(( grace * 4 ))
  while alive "$pid" && [ "$n" -gt 0 ]; do
    sleep 0.25
    n=$(( n - 1 ))
  done
  if alive "$pid"; then
    pkill -P "$pid" 2>/dev/null || true
    kill -9 "$pid" 2>/dev/null || true
  fi
}

cmd_stop() {
  stop_pid "$(find_autoapp)" "$AUTOAPP_MATCH" 10
  stop_pid "$(find_stream)" "$STREAM_MATCH" 10
  stop_pid "$(lock_pid fifo)" "" 2
  stop_pid "$(lock_pid caffeinate)" "caffeinate" 2

  # Orphans survive a lost lock file (nohup detaches them to pid 1).
  pkill -f "$AUTOAPP_PGREP" 2>/dev/null || true
  pkill -f "$STREAM_PGREP" 2>/dev/null || true

  rm -f "$FIFO" "$LOCK" /tmp/auriga-mac-autoapp.pid /tmp/auriga-mac-stream.pid \
    /tmp/auriga-mac-caffeinate.pid /tmp/auriga-fifo-writer.pid
  rm -rf "$START_GUARD"
  say "head unit stopped"
}

cmd_status() {
  ok=1
  echo "capture dir: $CAPTURE_DIR"
  if [ -p "$FIFO" ]; then echo "input fifo:  $FIFO"; else echo "input fifo:  $FIFO (missing)"; ok=0; fi

  p=$(find_autoapp)
  if [ -n "$p" ]; then echo "autoapp:     running (pid $p)"; else echo "autoapp:     stopped"; ok=0; fi

  s=$(find_stream)
  if [ -n "$s" ]; then echo "stream:      running (pid $s)"; else echo "stream:      stopped"; ok=0; fi

  if port_open "$HTTP_PORT"; then echo "http:        127.0.0.1:$HTTP_PORT listening"; else echo "http:        127.0.0.1:$HTTP_PORT closed"; ok=0; fi
  if port_open "$WS_PORT"; then echo "ws:          127.0.0.1:$WS_PORT listening"; else echo "ws:          127.0.0.1:$WS_PORT closed"; ok=0; fi

  if [ -e "$CAPTURE_DIR/current" ]; then
    echo "session:     $(readlink "$CAPTURE_DIR/current" 2>/dev/null || echo current)"
  else
    echo "session:     none yet"
  fi
  echo "logs:        $LOG_DIR"
  echo "lock:        $LOCK$([ -f "$LOCK" ] || echo ' (none)')"

  [ "$ok" -eq 1 ]
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  *)
    echo "usage: $(basename "$0") {start|stop|status}" >&2
    exit 2
    ;;
esac
