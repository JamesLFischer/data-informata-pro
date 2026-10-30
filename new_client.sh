#!/bin/sh
# Usage: ./new_client.sh <slug> "<Brand Name>" <domain> [--competitors "A, B, C"]
# Creates configs/<slug>.yaml (5 clusters x 5 TODO prompts), then prints the validate -> estimate -> smoke-test steps.
cd "$(dirname "$0")" && exec python3 -m aivis.newclient "$@"
