#!/bin/sh
# Profound Bot side: ./asks.sh pending | list [--all] | show <id> | context <slug> | answer <id> "text" | ask <slug> "question"
cd "$(dirname "$0")" && exec python3 -m aivis.asks "$@"
