#!/bin/sh
# Start the encrypted relay worker (public site <-> box via ntfy.sh, no inbound ports). Keep it running.
cd "$(dirname "$0")" && exec python3 -m aivis.relay
