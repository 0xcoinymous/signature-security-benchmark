#!/usr/bin/env python3
"""Manual-review table: for each reviewed detector, the contracts it flags in D1-D3 and D5, the sample,
the verdicts and the precision with a 95% Wilson interval.

    table.py --d5-dir <large dir> --thesis ../thesis/latex/tables/manual-review.tex \
             --paper ../paper/tables/manual-review.tex
"""
import argparse
import csv
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from make_paper_tables import DETECTOR_EN, num  # noqa: E402
from make_tables import DETECTOR_FA, FA_DIGITS, fa, rows  # noqa: E402
from sample import population  # noqa: E402

DETECTORS = ["signature-malleability", "eip712-implementation", "signature-freshness",
             "nonce-management", "eip1271-verification"]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d5-dir", required=True)
    ap.add_argument("--labelled-run", type=Path, default=HERE.parent / "results" / "run8")
    ap.add_argument("--large-run", type=Path, default=HERE.parent / "results" / "run9")
    ap.add_argument("--thesis", required=True, type=Path)
    ap.add_argument("--paper", required=True, type=Path)
    args = ap.parse_args()
    thesis, paper = [], []
    for det in DETECTORS:
        flagged = len(population(det, args.d5_dir, args.labelled_run, args.large_run))
        verdicts = [r["verdict"] for r in csv.DictReader(open(HERE / f"{det}.csv"))]
        weak, false = verdicts.count("weakness"), verdicts.count("false alarm")
        n = weak + false
        lo, hi = wilson(weak, n)
        flagged_fa = f"{flagged:,}".replace(",", "٬").translate(FA_DIGITS)
        thesis.append([DETECTOR_FA[det], flagged_fa, fa(len(verdicts)), fa(weak), fa(false),
                       f"{fa(weak / n)} [{fa(lo)}، {fa(hi)}]"])
        paper.append([DETECTOR_EN[det], f"{flagged:,}", str(len(verdicts)), str(weak), str(false),
                      f"{num(weak / n)} [{num(lo)}, {num(hi)}]"])
    args.thesis.write_text(rows(thesis), encoding="utf-8")
    paper_rows = "".join(" & ".join(cells) + r" \\" + "\n" for cells in paper) + "\\botrule\n"
    args.paper.write_text(paper_rows, encoding="utf-8")
    print(paper_rows)


if __name__ == "__main__":
    main()
