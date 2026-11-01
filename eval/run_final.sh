#!/usr/bin/env bash
# The final evaluation: extended Aderyn, stock Aderyn and Slither on the labelled datasets (results/run8),
# then extended Aderyn on the deployed contracts of four chains and stock Aderyn on the Ethereum part, one
# after the other, for the runtime comparison (results/run9).
#   run_final.sh <extended aderyn binary> <stock aderyn binary> <dir from `fetch.py large`>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EXTENDED="$1"; STOCK="$2"; LARGE="$3"
JOBS=4 "$HERE/run_datasets.sh" "$EXTENDED" "$STOCK" "$HERE/results/run8"
OUT="$HERE/results/run9"
for chain in Ethereum BSC Polygon Arbitrum; do
  common=(--contracts "$LARGE/$chain" --files "$OUT/files_$chain.txt" --compilers "$HERE/datasets/compilers.csv"
          --chain "$chain" --jobs 8)
  python3 "$HERE/run_dataset.py" aderyn --bin "$EXTENDED" "${common[@]}" --out "$OUT/${chain}_extended.json"
  if [ "$chain" = Ethereum ]; then
    python3 "$HERE/run_dataset.py" aderyn --bin "$STOCK" "${common[@]}" --out "$OUT/${chain}_stock.json"
  fi
done
