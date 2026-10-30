#!/bin/sh
# Start the relay if it isn't running, or restart it if its heartbeat is stale (stream hung). Safe to call repeatedly.
# cron: */2 * * * * /workspace/ai-visibility/relay_watchdog.sh   (no cron on the box: relay_keepalive.sh loops this every 60s)
cd "$(dirname "$0")"
LOG=/tmp/aivis_relay_watchdog.log; ST="${AIVIS_RELAY_STATUS:-/tmp/aivis_relay_status.json}"; STALE=300
pid=$(pgrep -f "python3 -m aivis.relay" | head -1)
if [ -n "$pid" ] && [ -f "$ST" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$ST") ))
  if [ "$age" -gt "$STALE" ]; then
    echo "$(date '+%F %T') relay heartbeat stale (${age}s) - restarting pid $pid" >> "$LOG"
    kill "$pid" 2>/dev/null; sleep 2; kill -9 "$pid" 2>/dev/null; pid=""
  fi
fi
[ -n "$pid" ] && exit 0
echo "$(date '+%F %T') relay down - starting" >> "$LOG"
nohup ./relay.sh >> /tmp/aivis_relay.log 2>&1 &
