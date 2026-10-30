#!/bin/sh
# Usage: ./new_client.sh <slug> "<Brand Name>" <domain>
# Creates configs/<slug>.yaml from _template.yaml. Then fill competitors/facts/prompts and run: ./run.sh <slug> --estimate
set -e; cd "$(dirname "$0")"
[ $# -eq 3 ] || { echo "usage: $0 <slug> \"<Brand Name>\" <domain>"; exit 1; }
f="configs/$1.yaml"; [ -e "$f" ] && { echo "$f exists"; exit 1; }
sed -e "s/^brand: .*/brand: $2/" -e "s/^domain: .*/domain: $3/" \
    -e 's/^placeholders_unconfirmed: .*/placeholders_unconfirmed: ["competitors list", "facts", "prompt set"]/' configs/_template.yaml > "$f"
echo "created $f - edit competitors, facts, and prompts (aim 25-50), then: ./run.sh $1 --estimate && ./run.sh $1 --limit 2"
