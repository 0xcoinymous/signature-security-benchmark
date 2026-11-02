#!/usr/bin/env python3
"""Pairs to re-examine: scored (contract, type) pairs labelled 0 by their source that a tool reports in the
findings view (extended Aderyn's detectors for the type, Slither's signature detectors).

    make_list.py --run results/run8 --out adjudication/adjudication.csv

Rows already present in the output keep their verdict and reason; a judged pair that no tool reports in
the given run stays in the file with reported_by "none", so its reviewed label is still used.
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from score_datasets import SLITHER_STRICT, TYPE_DETECTORS, detectors_by_file  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=HERE.parent / "results" / "run8")
    ap.add_argument("--combined", type=Path, default=HERE.parent / "datasets" / "combined.csv")
    ap.add_argument("--out", type=Path, default=HERE / "adjudication.csv")
    args = ap.parse_args()
    extended, _ = detectors_by_file(args.run / "extended.json")
    slither, _ = detectors_by_file(args.run / "slither.json")
    old = {}
    if args.out.exists():
        old = {(r["file"], r["type"]): r for r in csv.DictReader(open(args.out))}
    rows = []
    for r in csv.DictReader(open(args.combined)):
        if r["label"] != "0" or not TYPE_DETECTORS.get(r["type"]):
            continue
        by = []
        if extended.get(r["file"], set()) & TYPE_DETECTORS[r["type"]]:
            by.append("extended")
        if slither.get(r["file"], set()) & SLITHER_STRICT:
            by.append("slither")
        if not by:
            continue
        prev = old.get((r["file"], r["type"]), {})
        rows.append({"file": r["file"], "type": r["type"], "sources": r["sources"], "source_label": "0",
                     "reported_by": "+".join(by), "label": prev.get("label", ""),
                     "reason": prev.get("reason", "")})
    listed = {(r["file"], r["type"]) for r in rows}
    for key, prev in old.items():
        if key not in listed and prev.get("label"):
            rows.append({**prev, "reported_by": "none"})
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "type", "sources", "source_label", "reported_by", "label", "reason"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} pairs; {sum(1 for r in rows if r['label'])} already judged")


if __name__ == "__main__":
    main()
