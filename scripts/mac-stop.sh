#!/bin/sh
# Stop the Mac-side SSH tunnel.
set -eu

if [ -f /tmp/auriga-tunnel.pid ]; then
  kill "$(cat /tmp/auriga-tunnel.pid)" 2>/dev/null || true
  rm -f /tmp/auriga-tunnel.pid
  echo "tunnel stopped"
else
  echo "no tunnel pid file"
fi
