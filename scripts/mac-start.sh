#!/bin/sh
# Start the Mac side: SSH tunnel to the Pi and open the browser client.
# Run on the Mac: ./scripts/mac-start.sh
set -eu

HOST=${AURIGA_HOST:-pi@auriga-pi.local}

if ! nc -z 127.0.0.1 8080 >/dev/null 2>&1 || ! nc -z 127.0.0.1 8081 >/dev/null 2>&1; then
  if [ -f /tmp/auriga-tunnel.pid ]; then
    kill "$(cat /tmp/auriga-tunnel.pid)" 2>/dev/null || true
    rm -f /tmp/auriga-tunnel.pid
  fi
  ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -L 8080:127.0.0.1:8080 -L 8081:127.0.0.1:8081 "$HOST" &
  echo $! > /tmp/auriga-tunnel.pid
  echo "tunnel started (pid $(cat /tmp/auriga-tunnel.pid))"
  sleep 1
else
  echo "tunnel already listening on 8080/8081"
fi

if open -a "Brave Browser" "http://localhost:8080" 2>/dev/null; then
  echo "opened Brave at http://localhost:8080"
else
  open "http://localhost:8080"
  echo "opened default browser at http://localhost:8080"
fi
