#!/usr/bin/env bash
# Run every tool on the labelled datasets (D1-D3) and the audited contracts (D4), one file at a time.
#   run_datasets.sh <extended aderyn binary> <stock aderyn binary> [OUT dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CONTRACTS="$HERE/../../signature-security-benchmark/contracts"
EXTENDED="$1"; STOCK="$2"; OUT="${3:-$HERE/results/run8}"
JOBS="${JOBS:-6}"
mkdir -p "$OUT"
cat "$OUT/files_labelled.txt" "$OUT/files_D4.txt" > "$OUT/files_all.txt"
common=(--contracts "$CONTRACTS" --files "$OUT/files_all.txt" --compilers "$HERE/datasets/compilers.csv"
        --chain Ethereum --jobs "$JOBS")
python3 "$HERE/run_dataset.py" aderyn --bin "$EXTENDED" "${common[@]}" --out "$OUT/extended.json"
python3 "$HERE/run_dataset.py" aderyn --bin "$STOCK" "${common[@]}" --out "$OUT/stock.json"
python3 "$HERE/run_dataset.py" slither --installer "$EXTENDED" "${common[@]}" --out "$OUT/slither.json"
