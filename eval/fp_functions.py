#!/usr/bin/env python3
"""Functions in which the replay and nonce detectors report on pairs of the general replay type.

    fp_functions.py --run results/run4 --contracts ../../signature-security-benchmark/contracts \
                    --out ../thesis/latex/tables/fp-functions.tex

For every pair of type `replay` that the extended build flags, the name of the function enclosing each
finding of the two detectors is read from the source (the nearest `function` line above it). The table
lists, for the most frequent names among false positives, in how many contracts the name appears among
false positives and among true positives.
"""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from make_tables import fa, rows
from run_dataset import project_sources

DETECTORS = {"signature-replay", "nonce-management"}


def enclosing_function(text, line):
    lines = text.splitlines()
    for i in range(min(line, len(lines)) - 1, -1, -1):
        match = re.search(r"\bfunction\s+([A-Za-z_]\w*)", lines[i])
        if match:
            return match.group(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--contracts", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()
    per_row = list(csv.DictReader((args.run / "datasets_per_row.csv").open()))
    extended = json.loads((args.run / "extended.json").read_text())

    def names(file_name):
        result = extended[file_name]
        files, _ = project_sources(args.contracts / file_name)[result.get("variant", 0)]
        found = set()
        for detector, line, path in result.get("findings", []):
            if detector in DETECTORS:
                text = files.get(path) or next(iter(files.values()))
                found.add(enclosing_function(text, line))
        return found - {None}

    flagged = [r for r in per_row if r["type"] == "replay" and r["extended"] == "1"]
    fp = Counter(n for r in flagged if r["label"] == "0" for n in names(r["file"]))
    tp = Counter(n for r in flagged if r["label"] == "1" for n in names(r["file"]))
    out = [[rf"\code{{{name}}}", fa(count), fa(tp.get(name, 0))] for name, count in fp.most_common(args.top)]
    args.out.write_text(rows(out), encoding="utf-8")
    print(fp.most_common(args.top), {n: tp.get(n, 0) for n, _ in fp.most_common(args.top)})


if __name__ == "__main__":
    main()
