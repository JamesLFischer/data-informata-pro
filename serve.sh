#!/bin/sh
# Dashboard + "Ask Profound Bot" API at http://127.0.0.1:${PORT:-8000} (local only). Static docs/ still works on its own.
cd "$(dirname "$0")" && exec python3 -m aivis.server
