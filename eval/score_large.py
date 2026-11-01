#!/usr/bin/env python3
"""Scale, runtime and number of findings on the large unlabelled set (contracts that call ecrecover on
Ethereum, BSC, Polygon and Arbitrum).

    score_large.py --runs results/run9 --lasir-dir datasets/raw/lasir --out results/run9

Reads <runs>/<Chain>_extended.json for every chain and <Chain>_stock.json for the runtime chain, written
by run_dataset.py. The contracts confirmed exploitable in the source study belong to the labelled evaluation
dataset and are left out here. There are no labels, so only the number of contracts in which a tool
reports something is given, never accuracy. Runtime is compared on Ethereum, the only chain on which the
two Aderyn builds ran one after the other under the same load (the other chains ran in parallel).
"""
import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from score_datasets import SIX

CHAINS = ["Ethereum", "BSC", "Polygon", "Arbitrum"]
TOOLS = ["extended", "stock", "slither"]
RUNTIME_CHAIN = "Ethereum"


def confirmed_exploitable(lasir_dir):
    """{(chain, lower-case address)} of the contracts the source study confirmed exploitable."""
    rows = csv.DictReader(open(Path(lasir_dir) / "RQ1_Manual_analysis.csv", encoding="utf-8-sig"))
    return {(row["Blockchain"].strip(), row["Address"].strip().lower()) for row in rows}


def runtime(seconds):
    if not seconds:
        return {}
    ordered = sorted(seconds)
    return {"median": statistics.median(ordered), "mean": statistics.mean(ordered),
            "p95": ordered[math.ceil(0.95 * len(ordered)) - 1], "max": ordered[-1],
            "total_hours": sum(ordered) / 3600, "n": len(ordered)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--lasir-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    runs = Path(args.runs)
    confirmed = confirmed_exploitable(args.lasir_dir)
    summary = {}
    total = {"files": 0, "analysed": Counter(), "flagged_any_of_six": 0, "per_detector": Counter()}
    seconds = {tool: [] for tool in TOOLS}
    for chain in CHAINS:
        names = [n.strip() for n in (runs / f"files_{chain}.txt").read_text().splitlines() if n.strip()]
        names = [n for n in names if (chain, n.split("_", 1)[0].lower()) not in confirmed]
        tools = ["extended", "stock"] if chain == RUNTIME_CHAIN else ["extended"]
        results = {tool: json.loads((runs / f"{chain}_{tool}.json").read_text()) for tool in tools}

        def found(tool, name):
            return {f[0] for f in results[tool].get(name, {}).get("findings", [])}

        entry = {
            "files": len(names),
            "analysed": {tool: sum("findings" in results[tool].get(n, {}) for n in names) for tool in results},
            "flagged_any_of_six": sum(bool(found("extended", n) & set(SIX)) for n in names),
            "per_detector": dict(Counter(d for n in names for d in found("extended", n) & set(SIX))),
            "runtime_seconds": {},
        }
        for tool in results:
            chain_seconds = [results[tool][n]["seconds"] for n in names if "findings" in results[tool].get(n, {})]
            entry["runtime_seconds"][tool] = runtime(chain_seconds)
            if chain == RUNTIME_CHAIN:
                seconds[tool] += chain_seconds
        summary[chain] = entry
        total["files"] += entry["files"]
        total["analysed"].update(entry["analysed"])
        total["flagged_any_of_six"] += entry["flagged_any_of_six"]
        total["per_detector"].update(entry["per_detector"])
    total["analysed"] = dict(total["analysed"])
    total["per_detector"] = dict(total["per_detector"])
    total["runtime_seconds"] = {tool: runtime(seconds[tool]) for tool in TOOLS if seconds[tool]}
    total["runtime_chain"] = RUNTIME_CHAIN
    summary["total"] = total
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "large_summary.json").write_text(json.dumps(summary, indent=1))
    for chain in CHAINS + ["total"]:
        e = summary[chain]
        print(f"{chain:9} files={e['files']:6} analysed={e['analysed']} any-of-six={e['flagged_any_of_six']:6}")
    print({tool: {k: round(v, 2) for k, v in r.items()} for tool, r in total["runtime_seconds"].items()})


if __name__ == "__main__":
    main()
