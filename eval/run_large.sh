#!/usr/bin/env bash
# Run extended Aderyn, stock Aderyn and Slither on the large unlabelled set, one file at a time.
#   run_large.sh <extended aderyn binary> <stock aderyn binary> <dir from `fetch.py large`> [OUT dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EXTENDED="$1"; STOCK="$2"; LARGE="$3"; OUT="${4:-$HERE/results/run5}"
JOBS="${JOBS:-6}"
mkdir -p "$OUT"
for chain in Ethereum BSC Polygon Arbitrum; do
    common=(--contracts "$LARGE/$chain" --files "$OUT/files_$chain.txt" --compilers "$HERE/datasets/compilers.csv"
            --chain "$chain" --jobs "$JOBS")
    python3 "$HERE/run_dataset.py" aderyn --bin "$EXTENDED" "${common[@]}" --out "$OUT/${chain}_extended.json"
    python3 "$HERE/run_dataset.py" aderyn --bin "$STOCK" "${common[@]}" --out "$OUT/${chain}_stock.json"
done
for chain in Ethereum BSC Polygon Arbitrum; do
    python3 "$HERE/run_dataset.py" slither --installer "$EXTENDED" --contracts "$LARGE/$chain" \
        --files "$OUT/files_$chain.txt" --compilers "$HERE/datasets/compilers.csv" --chain "$chain" \
        --jobs "$JOBS" --out "$OUT/${chain}_slither.json"
done
