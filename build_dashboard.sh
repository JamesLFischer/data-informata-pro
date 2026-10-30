#!/bin/sh
# Rebuild private_site/ (client data, gitignored, served by ./serve.sh behind login). docs/ is the public shell.
cd "$(dirname "$0")" && python3 -m aivis.dashboard "$@"
