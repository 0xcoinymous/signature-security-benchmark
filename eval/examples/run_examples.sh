#!/usr/bin/env bash
# Run an Aderyn binary on the thesis chapter-3 examples (one project per example and version, so that
# library names of different examples never meet) and print the signature-related detectors that fire.
#   run_examples.sh <aderyn-binary>
set -euo pipefail
BIN=$(realpath "$1")
HERE=$(dirname "$(realpath "$0")")
TMP=$(mktemp -d)
for dir in "$HERE"/*/*/; do
  name=$(basename "$(dirname "$dir")")/$(basename "$dir")
  "$BIN" "$dir" -s contracts -o "$TMP/out.json" > /dev/null 2>&1
  found=$(python3 -c "
import json
d = json.load(open('$TMP/out.json'))
names = {i['detector_name'] for k in ('high_issues', 'low_issues') for i in d.get(k, {}).get('issues', [])}
print(' '.join(sorted(n for n in names if any(x in n for x in ('signature', 'nonce', 'eip', 'ecrecover')))))")
  printf "%-32s %s\n" "$name" "$found"
done
rm -rf "$TMP"
