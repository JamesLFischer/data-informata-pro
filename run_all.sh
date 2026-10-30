#!/bin/sh
# Monthly batch: run every client config (skips _template). Extra args pass through, e.g. --engines gemini
cd "$(dirname "$0")"
for f in configs/*.yaml; do
  s=$(basename "$f" .yaml); case "$s" in _*) continue;; esac
  echo "=== $s ==="; ./run.sh "$s" "$@" || echo "!!! $s failed"
done
