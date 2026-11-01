#!/usr/bin/env bash
# Run every tool on the labelled datasets (D1-D3) and the audited contracts (D4), one file at a time.
#   run_datasets.sh <aderyn v3.1 binary> <stock aderyn binary> [<aderyn v3 binary>] [OUT dir]
# The optional v3 binary is the build before the expansion bound; its output is compared with v3.1.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CONTRACTS="$HERE/../../signature-security-benchmark/contracts"
EXTENDED="$1"; STOCK="$2"; V3="${3:-}"; OUT="${4:-$HERE/results/run4}"
JOBS="${JOBS:-6}"
mkdir -p "$OUT"
cat "$OUT/files_labelled.txt" "$OUT/files_D4.txt" > "$OUT/files_all.txt"
common=(--contracts "$CONTRACTS" --files "$OUT/files_all.txt" --compilers "$HERE/datasets/compilers.csv"
        --chain Ethereum --jobs "$JOBS")
python3 "$HERE/run_dataset.py" aderyn --bin "$EXTENDED" "${common[@]}" --out "$OUT/extended.json"
python3 "$HERE/run_dataset.py" aderyn --bin "$STOCK" "${common[@]}" --out "$OUT/stock.json"
python3 "$HERE/run_dataset.py" slither --installer "$EXTENDED" "${common[@]}" --out "$OUT/slither.json"
if [ -n "$V3" ]; then
    python3 "$HERE/run_dataset.py" aderyn --bin "$V3" "${common[@]}" --out "$OUT/extended_v3.json"
fi
