#!/bin/sh
# Profound Bot's side of the bridge: ./asks.sh list | show <id> | context <slug> | answer <id> "text" | ask <slug> "question"
cd "$(dirname "$0")" && exec python3 -m aivis.asks "$@"
