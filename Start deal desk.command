#!/bin/bash
# Double-click to open the Morocco deal desk in your browser. Close this window to stop it.
APP="$(cd "$(dirname "$0")/app" && pwd)"
PORT=8791
if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/profile"; then
  open "http://127.0.0.1:$PORT"; exit 0
fi
(sleep 1; open "http://127.0.0.1:$PORT") &
exec python3 "$APP/server.py" "$PORT"
