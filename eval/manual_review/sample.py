#!/usr/bin/env python3
"""Draw the findings of one detector that are checked by hand.

    sample.py --detector signature-freshness --n 30 --seed 1404 --d5-dir <large dir> \
              --out manual_review/signature-freshness.csv

The population is every contract of D1-D3 (--labelled-run, default results/run6) and D5
(--large-run, default results/run7) that the extended build flags with the detector. Contracts are
drawn uniformly without replacement, and one reported instance is drawn from each. The source shown
for review is the file exactly as it was analysed (the same preparation as run_dataset.py), so line
numbers match the finding.
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from run_dataset import SRC, project_sources  # noqa: E402

# The contracts sit next to eval/ in the benchmark repository and in signature-security-benchmark/ of the
# Aderyn fork.
CONTRACTS = next((p for p in (HERE.parents[1] / "contracts",
                              HERE.parents[2] / "signature-security-benchmark" / "contracts") if p.exists()),
                 HERE.parents[1] / "contracts")
CHAINS = ["Ethereum", "BSC", "Polygon", "Arbitrum"]


def population(detector, d5_dir, labelled_run, large_run):
    labelled = set((labelled_run / "files_labelled.txt").read_text().split())
    out = []
    ext = json.loads((labelled_run / "extended.json").read_text())
    for name in sorted(labelled):
        hits = [f for f in ext.get(name, {}).get("findings", []) if f[0] == detector]
        if hits:
            out.append(("D1-D3", CONTRACTS / name, ext[name], hits))
    for chain in CHAINS:
        path = large_run / f"{chain}_extended.json"
        if not path.exists():
            continue
        results = json.loads(path.read_text())
        for name in sorted(results):
            hits = [f for f in results[name].get("findings", []) if f[0] == detector]
            if hits:
                out.append((f"D5-{chain}", Path(d5_dir) / chain / name, results[name], hits))
    return out


def snippet(path, result, finding, context=12):
    variants = project_sources(path)
    files, _ = variants[result.get("variant", 0)]
    _, line, rel = finding
    text = files.get(rel) or files.get(rel.removeprefix(f"{SRC}/")) or next(iter(files.values()))
    lines = text.splitlines()
    lo, hi = max(0, line - context - 1), min(len(lines), line + context)
    return "\n".join(f"{i + 1:5}{'>' if i + 1 == line else ' '} {lines[i]}" for i in range(lo, hi))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1404)
    ap.add_argument("--d5-dir", required=True)
    ap.add_argument("--labelled-run", type=Path, default=HERE.parent / "results" / "run6")
    ap.add_argument("--large-run", type=Path, default=HERE.parent / "results" / "run7")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pool = population(args.detector, args.d5_dir, args.labelled_run, args.large_run)
    rng = random.Random(args.seed)
    picked = rng.sample(pool, min(args.n, len(pool)))
    out = Path(args.out)
    snippets = out.with_suffix("")
    snippets.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (dataset, path, result, hits) in enumerate(picked, 1):
        finding = rng.choice(hits)
        case = f"{i:02d}"
        (snippets / f"{case}.txt").write_text(
            f"{dataset}  {path.name}  {finding[2]}:{finding[1]}  (solc {result.get('solc')})\n\n"
            + snippet(path, result, finding) + "\n")
        rows.append({"case": case, "dataset": dataset, "file": path.name, "path": finding[2],
                     "line": finding[1], "verdict": "", "reason": "", "confirmed_by_student": ""})
    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.detector}: population {len(pool)} contracts, sampled {len(rows)}")


if __name__ == "__main__":
    main()
