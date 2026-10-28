#!/bin/sh
# Stop the local macOS head unit started by scripts/mac-headunit-start.sh.
# Does not touch the Pi stack or a Pi SSH tunnel.
set -eu

stop_pidfile() {
  [ -f "$1" ] || return 0
  pid=$(cat "$1" 2>/dev/null || true)
  if [ -n "${pid:-}" ]; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$1"
}

# run-mac.sh execs autoapp, so the pidfile may point at the shell wrapper.
stop_pidfile /tmp/auriga-mac-autoapp.pid
stop_pidfile /tmp/auriga-mac-stream.pid
stop_pidfile /tmp/auriga-mac-caffeinate.pid
stop_pidfile /tmp/auriga-fifo-writer.pid

pkill -f "[b]uild-openauto-mac/bin/autoapp" 2>/dev/null || true
pkill -f "[a]uriga_stream.py --video" 2>/dev/null || true

echo "Mac head unit stopped."
