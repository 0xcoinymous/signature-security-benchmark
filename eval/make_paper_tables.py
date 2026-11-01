#!/usr/bin/env python3
"""Generate the English table bodies and chart data of the journal article.

    make_paper_tables.py --run results/run8 --large results/run9 --combined datasets/combined.csv \
                         --out ../paper/tables

The same summaries as the thesis tables (make_tables.py) are used, so both report identical numbers:
datasets_summary.json written by score_datasets.py, large_summary.json written by score_large.py and the
per-contract times of the tool runs. The rows and the closing rule are written; the table environments and
headers live in the article sources.
"""
import argparse
import csv
import json
import math
from pathlib import Path

from make_tables import labelled_runtime
from score_datasets import TYPE_DETECTORS

TYPE_EN = {
    "replay": "Signature replay (general)",
    "replay_single": "Replay within a contract",
    "replay_cross_contract": "Cross-contract replay",
    "replay_cross_chain": "Cross-chain replay",
    "malleability": "Signature malleability",
    "insufficient_verification": "Insufficient verification",
    "frontrunning": "Signature front-running",
}
DETECTOR_EN = {
    "signature-replay": "replay",
    "signature-malleability": "malleability",
    "nonce-management": "nonce",
    "eip712-implementation": "EIP-712",
    "eip1271-verification": "ERC-1271",
    "signature-freshness": "freshness",
}
TOOL_EN = {"extended": "Extended Aderyn", "stock": "Stock Aderyn", "slither": "Slither"}
VIEW_EN = {"findings": "Vulnerability findings", "all": "All outputs"}
TYPES = ["replay", "replay_single", "replay_cross_contract", "replay_cross_chain", "malleability"]
TOOLS = ["extended", "stock", "slither"]


def num(x, digits=2):
    if isinstance(x, float):
        return "--" if math.isnan(x) else f"{x:.{digits}f}"
    return f"{x:,}"


def pval(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def rows(lines):
    return "\n".join(" & ".join(cells) + r" \\" for cells in lines) + "\n"


def types_table(summary):
    out = []
    for vtype, name in TYPE_EN.items():
        counts = summary["dataset"]["pairs_by_type"][vtype]
        detectors = ", ".join(DETECTOR_EN[d] for d in DETECTOR_EN if d in TYPE_DETECTORS[vtype]) or "none"
        out.append([name, num(counts["n"]), num(counts["positive"]), detectors])
    return rows(out)


def overall_table(summary):
    blocks = []
    for view in ("findings", "all"):
        out = []
        for i, tool in enumerate(TOOLS):
            m = summary["views"][view]["overall"][tool]
            label = rf"\multirow{{3}}{{*}}{{{VIEW_EN[view]}}}" if i == 0 else ""
            out.append([label, TOOL_EN[tool], num(m["tp"]), num(m["fp"]), num(m["fn"]), num(m["tn"]),
                        num(m["precision"]), num(m["recall"]), num(m["f1"]), num(m["accuracy"])])
        blocks.append(rows(out))
    return "\\midrule\n".join(blocks)


def bytype_table(summary):
    out = []
    for vtype in TYPES:
        e = summary["views"]["findings"]["by_type"][vtype]
        counts = summary["dataset"]["pairs_by_type"][vtype]
        a = summary["views"]["all"]["by_type"][vtype]
        out.append([TYPE_EN[vtype], num(counts["n"]), num(counts["positive"]),
                    num(e["extended"]["precision"]), num(e["extended"]["recall"]), num(e["extended"]["f1"]),
                    num(e["slither"]["precision"]), num(e["slither"]["recall"]), num(e["slither"]["f1"]),
                    num(a["stock"]["f1"])])
    return rows(out)


def mcnemar_table(summary):
    out = []
    for view in ("findings", "all"):
        for other in ("stock", "slither"):
            test = summary["views"][view]["mcnemar"][f"extended_vs_{other}"]
            a, p = test["all_pairs"], test["positive_pairs"]
            out.append([VIEW_EN[view], TOOL_EN[other], num(a["a_only_correct"]), num(a["b_only_correct"]),
                        pval(a["p_value"]), num(p["a_only_correct"]), num(p["b_only_correct"]),
                        pval(p["p_value"])])
    return rows(out)


def detector_table(summary):
    out = []
    for det, name in DETECTOR_EN.items():
        m = summary["per_detector"][det]
        out.append([name, num(m["contracts_flagged"]), num(m["precision"]), num(m["recall"])])
    return rows(out)


def runtime_table(labelled, large):
    out = []
    for tool in TOOLS:
        big = large["total"]["runtime_seconds"].get(tool)
        out.append([TOOL_EN[tool], num(labelled[tool]["median"]), num(labelled[tool]["mean"]),
                    num(big["median"]) if big else "--", num(big["mean"]) if big else "--"])
    return rows(out)


def runtime_quantiles(run, combined, steps=100):
    """Seconds per analysed contract at each percentile, for the distribution plot of the evaluation set."""
    files = sorted({r["file"] for r in combined})
    columns = {}
    for tool in TOOLS:
        data = json.loads((run / f"{tool}.json").read_text())
        seconds = sorted(data[f]["seconds"] for f in files if "findings" in data.get(f, {}))
        columns[tool] = [seconds[min(len(seconds) - 1, math.ceil(q / steps * len(seconds)) - 1)]
                         for q in range(1, steps + 1)]
    lines = ["share " + " ".join(TOOLS)]
    for i in range(steps):
        lines.append(f"{(i + 1) / steps:.2f} " + " ".join(f"{columns[t][i]:.2f}" for t in TOOLS))
    return "\n".join(lines) + "\n"


def chart_data(summary):
    lines = ["type ext slither stockall"]
    for i, vtype in enumerate(TYPES, 1):
        e = summary["views"]["findings"]["by_type"][vtype]
        a = summary["views"]["all"]["by_type"][vtype]
        lines.append(f"{i} {e['extended']['f1']:.3f} {e['slither']['f1']:.3f} {a['stock']['f1']:.3f}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--large", required=True, type=Path)
    ap.add_argument("--combined", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    summary = json.loads((args.run / "datasets_summary.json").read_text())
    large = json.loads((args.large / "large_summary.json").read_text())
    combined = list(csv.DictReader(args.combined.open()))
    tables = {
        "types.tex": types_table(summary),
        "overall.tex": overall_table(summary),
        "bytype.tex": bytype_table(summary),
        "mcnemar.tex": mcnemar_table(summary),
        "detectors.tex": detector_table(summary),
        "runtime.tex": runtime_table(labelled_runtime(args.run, combined), large),
        "chart-type.dat": chart_data(summary),
        "runtime-quantiles.dat": runtime_quantiles(args.run, combined),
    }
    for name, text in tables.items():
        # A table's closing rule must follow its last row directly, so it is part of the generated rows.
        (args.out / name).write_text(text + ("\\botrule\n" if name.endswith(".tex") else ""))
    print("written:", ", ".join(sorted(tables)))


if __name__ == "__main__":
    main()
