#!/bin/sh
# No cron on the box: run this once in the background; it checks every 60s. Start: nohup ./relay_keepalive.sh >/dev/null 2>&1 &
cd "$(dirname "$0")"
while true; do ./relay_watchdog.sh; sleep 60; done
