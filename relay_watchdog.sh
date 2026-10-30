#!/bin/sh
# Start the relay if it isn't running. Safe to call repeatedly (cron: */2 * * * * /workspace/ai-visibility/relay_watchdog.sh)
cd "$(dirname "$0")"
pgrep -f "python3 -m aivis.relay" >/dev/null && exit 0
echo "$(date '+%F %T') relay down - starting" >> /tmp/aivis_relay_watchdog.log
nohup ./relay.sh >> /tmp/aivis_relay.log 2>&1 &
