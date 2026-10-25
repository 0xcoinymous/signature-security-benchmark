#!/usr/bin/env python3
"""Score extended Aderyn, stock Aderyn and Slither on the combined evaluation dataset.

    score_datasets.py --combined datasets/combined.csv --run results/run4 --out results/run4

The unit is a labelled (contract, vulnerability type) pair (datasets/combined.csv). A pair is flagged
when the tool reports, anywhere in the contract, a detector that counts for the type. Two views:
  findings  what each tool reports as a vulnerability: the six High detectors of the extended build;
            stock Aderyn has no High detector for these types; Slither's signature-specific
            High/Medium detectors.
  all       every output, including stock Aderyn's Low `ecrecover` note (raised on every call) and the
            wider Slither set.
The type -> detector mapping was fixed before the tools were run. A file a tool could not analyse counts
as not flagged. Types no detector targets are listed but not scored.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from scipy.stats import binomtest

SIX = ["signature-replay", "signature-malleability", "nonce-management",
       "eip712-implementation", "eip1271-verification", "signature-freshness"]
TYPE_DETECTORS = {
    # Signature replay in the broad sense (within the contract, across contracts and chains,
    # contract accounts, state management, malleable signatures used as identities).
    "replay": {"signature-replay", "nonce-management", "signature-malleability",
               "eip1271-verification", "eip712-implementation"},
    "replay_single": {"signature-replay", "nonce-management"},
    "replay_cross_contract": {"signature-replay", "eip712-implementation"},
    "replay_cross_chain": {"signature-replay", "eip712-implementation"},
    "malleability": {"signature-malleability"},
    "insufficient_verification": set(),
    "frontrunning": set(),
}
TYPES = [t for t, d in TYPE_DETECTORS.items() if d]
SLITHER_STRICT = {"encode-packed-collision", "arbitrary-send-erc20-permit", "domain-separator-collision"}
SLITHER_LENIENT = SLITHER_STRICT | {"timestamp", "unchecked-lowlevel", "unused-return"}
VIEWS = {
    "findings": {"extended": None, "stock": set(), "slither": SLITHER_STRICT},
    "all": {"extended": None, "stock": {"ecrecover"}, "slither": SLITHER_LENIENT},
}
TOOLS = ["extended", "stock", "slither"]


def detectors_by_file(path):
    data = json.loads(Path(path).read_text())
    out, errors = {}, set()
    for name, result in data.items():
        if "error" in result:
            errors.add(name)
            out[name] = set()
        else:
            out[name] = {finding[0] for finding in result["findings"]}
    return out, errors


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def metrics(pairs):
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if not y and p)
    fn = sum(1 for y, p in pairs if y and not p)
    tn = sum(1 for y, p in pairs if not y and not p)
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision,
            "recall": recall, "f1": f1, "accuracy": (tp + tn) / len(pairs) if pairs else float("nan"),
            "fpr": fp / (fp + tn) if fp + tn else float("nan"),
            "precision_ci": wilson(tp, tp + fp), "recall_ci": wilson(tp, tp + fn)}


def mcnemar(labels, a, b, positives_only=False):
    """Exact McNemar test: pairs only one tool gets right (on all pairs, or on the positive pairs)."""
    rows = [(y, x, z) for y, x, z in zip(labels, a, b) if y or not positives_only]
    a_only = sum(1 for y, x, z in rows if x == y and z != y)
    b_only = sum(1 for y, x, z in rows if z == y and x != y)
    p = binomtest(min(a_only, b_only), a_only + b_only, 0.5).pvalue if a_only + b_only else 1.0
    return {"n": len(rows), "a_only_correct": a_only, "b_only_correct": b_only, "p_value": p}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combined", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run = Path(args.run)
    found, errors = {}, {}
    for tool in TOOLS:
        found[tool], errors[tool] = detectors_by_file(run / f"{tool}.json")
    rows = list(csv.DictReader(open(args.combined)))
    scored = [r for r in rows if TYPE_DETECTORS[r["type"]]]
    files = sorted({r["file"] for r in rows})

    def predict(view, tool, row):
        counted = TYPE_DETECTORS[row["type"]] if tool == "extended" else VIEWS[view][tool]
        return int(bool(found[tool].get(row["file"], set()) & counted))

    summary = {
        "dataset": {"contracts": len(files), "pairs": len(rows), "positive_pairs": sum(int(r["label"]) for r in rows),
                    "scored_pairs": len(scored), "scored_positive": sum(int(r["label"]) for r in scored),
                    "pairs_by_type": {t: {"n": sum(r["type"] == t for r in rows),
                                          "positive": sum(r["type"] == t and r["label"] == "1" for r in rows)}
                                      for t in TYPE_DETECTORS},
                    "contracts_by_chain": {c: len({r["file"] for r in rows if r["chain"] == c})
                                           for c in sorted({r["chain"] for r in rows})},
                    "contracts_by_source": {s: len({r["file"] for r in rows if s in r["sources"].split("+")})
                                            for s in sorted({x for r in rows for x in r["sources"].split("+")})}},
        "analysed": {tool: sum(f not in errors[tool] and f in found[tool] for f in files) for tool in TOOLS},
        "views": {},
    }
    per_row = []
    for view in VIEWS:
        y = [int(r["label"]) for r in scored]
        preds = {tool: [predict(view, tool, r) for r in scored] for tool in TOOLS}
        entry = {"overall": {tool: metrics(list(zip(y, p))) for tool, p in preds.items()}, "by_type": {},
                 "by_source": {}, "mcnemar": {}}
        for other in ("stock", "slither"):
            entry["mcnemar"][f"extended_vs_{other}"] = {
                "all_pairs": mcnemar(y, preds["extended"], preds[other]),
                "positive_pairs": mcnemar(y, preds["extended"], preds[other], positives_only=True)}
        entry["mcnemar_by_type"] = {}
        for vtype in TYPES:
            idx = [i for i, r in enumerate(scored) if r["type"] == vtype]
            entry["by_type"][vtype] = {tool: metrics([(y[i], preds[tool][i]) for i in idx]) for tool in TOOLS}
            entry["mcnemar_by_type"][vtype] = {
                f"extended_vs_{other}": {
                    "all_pairs": mcnemar([y[i] for i in idx], [preds["extended"][i] for i in idx],
                                         [preds[other][i] for i in idx]),
                    "positive_pairs": mcnemar([y[i] for i in idx], [preds["extended"][i] for i in idx],
                                              [preds[other][i] for i in idx], positives_only=True)}
                for other in ("stock", "slither")}
        for source in summary["dataset"]["contracts_by_source"]:
            idx = [i for i, r in enumerate(scored) if source in r["sources"].split("+")]
            entry["by_source"][source] = {tool: metrics([(y[i], preds[tool][i]) for i in idx]) for tool in TOOLS}
        summary["views"][view] = entry
        if view == "findings":
            for i, r in enumerate(scored):
                per_row.append({**r, **{tool: preds[tool][i] for tool in TOOLS},
                                "extended_detectors": ";".join(sorted(found["extended"].get(r["file"], set()) & set(SIX)))})
    # Each detector alone on the types it counts for (findings view), for the per-detector discussion.
    y = [int(r["label"]) for r in scored]
    summary["per_detector"] = {}
    for det in SIX:
        idx = [i for i, r in enumerate(scored) if det in TYPE_DETECTORS[r["type"]]]
        summary["per_detector"][det] = metrics([(y[i], int(det in found["extended"].get(scored[i]["file"], set())))
                                                for i in idx])
        summary["per_detector"][det]["contracts_flagged"] = sum(det in found["extended"].get(f, set()) for f in files)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "datasets_summary.json").write_text(json.dumps(summary, indent=1))
    with open(out / "datasets_per_row.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(per_row[0]))
        writer.writeheader()
        writer.writerows(per_row)
    for view, entry in summary["views"].items():
        for tool, m in entry["overall"].items():
            print(f"{view:8} {tool:8} TP={m['tp']:4} FP={m['fp']:4} FN={m['fn']:4} TN={m['tn']:4} "
                  f"P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} Acc={m['accuracy']:.3f}")
        for key, test in entry["mcnemar"].items():
            print(f"   {key}: all p={test['all_pairs']['p_value']:.2e} "
                  f"({test['all_pairs']['a_only_correct']}/{test['all_pairs']['b_only_correct']}), "
                  f"positives p={test['positive_pairs']['p_value']:.2e} "
                  f"({test['positive_pairs']['a_only_correct']}/{test['positive_pairs']['b_only_correct']})")


if __name__ == "__main__":
    main()
