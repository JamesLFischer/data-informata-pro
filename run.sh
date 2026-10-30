#!/bin/sh
# Usage: ./run.sh <client-slug|config.yaml> [options]   |   ./run.sh --list
# Keys: .env (gitignored) or one-file-per-key in $AIVIS_SECRETS_DIR (default /home/box/.secrets). Never commit keys.
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }
SD="${AIVIS_SECRETS_DIR:-/home/box/.secrets}"
for k in GEMINI_API_KEY OPENAI_API_KEY PERPLEXITY_API_KEY ANTHROPIC_API_KEY; do
  eval "v=\${$k:-}"; [ -z "$v" ] && [ -r "$SD/$k" ] && export "$k=$(cat "$SD/$k")"
done
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
exec $PY -m aivis.cli "$@"
