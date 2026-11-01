#!/usr/bin/env python3
"""Generate the chapter-3 and chapter-4 table bodies (LaTeX rows with Persian digits) and chart data.

    make_tables.py --run results/run4 --large results/run5 --combined datasets/combined.csv \
                   --out ../thesis/latex/tables

Every number comes from datasets_summary.json (score_datasets.py), large_summary.json (score_large.py)
and combined.csv, so re-running this script after a new evaluation updates the thesis. Only the rows are
written; the table environments and headers live in the chapter files.
"""
import argparse
import csv
import json
import math
from pathlib import Path

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
TYPE_FA = {
    "replay": "بازپخش امضا (کلی)",
    "replay_single": "بازپخش درون‌قراردادی",
    "replay_cross_contract": "بازپخش بین‌قراردادی",
    "replay_cross_chain": "بازپخش بین‌زنجیره‌ای",
    "malleability": "شکل‌پذیری امضا",
    "insufficient_verification": "بررسی ناکافی امضا",
    "frontrunning": r"\lr{Front-running} امضا",
}
DETECTOR_FA = {
    "signature-replay": "بازپخش امضا",
    "signature-malleability": "شکل‌پذیری امضا",
    "nonce-management": "مدیریت نانس",
    "eip712-implementation": r"پیاده‌سازی \std{EIP-712}",
    "eip1271-verification": r"تأیید \std{ERC-1271}",
    "signature-freshness": "تازگی امضا",
}
TOOL_FA = {"extended": "آدرین گسترش‌یافته", "stock": "نسخۀ اصلی آدرین", "slither": "اسلیتر"}
SOURCE_FA = {
    "S1": (r"نمونۀ تصادفی قراردادهای اتریوم با برچسب بازپخش امضا \cite{wang2026signaturereplay}"),
    "S2": (r"نمونۀ تصادفی قراردادهای رمزنگاری با برچسب همۀ انواع نقص امضا \cite{zhang2025cryptofails}"),
    "S3": (r"گزارش‌های نقص امضا که با بازبینی دستی تأیید یا رد شده‌اند \cite{zhang2025cryptofails}"),
    "S4": (r"قراردادهای آدیت‌شده \cite{zheng2024dappscan} و قراردادهای پرکاربرد"),
    "S5": (r"قراردادهای قابل سوءاستفاده، تأییدشده با شبیه‌سازی روی شبکه \cite{wang2026signaturereplay}"),
}
CHAIN_FA = {"Ethereum": "اتریوم", "BSC": "زنجیرۀ هوشمند بایننس", "Polygon": "پالیگان", "Arbitrum": "آربیتروم"}
TYPES = ["replay", "replay_single", "replay_cross_contract", "replay_cross_chain", "malleability"]
TOOLS = ["extended", "stock", "slither"]


def fa(x, digits=2):
    """Persian number; decimals use '/' as in the rest of the thesis, NaN becomes a dash."""
    if isinstance(x, float):
        if math.isnan(x):
            return "—"
        s = f"{x:.{digits}f}".replace(".", "/")
    elif isinstance(x, int) and x >= 10000:
        s = f"{x:,}".replace(",", "٬")
    else:
        s = str(x)
    return s.translate(FA_DIGITS)


def fa_p(p):
    return "کمتر از ۰/۰۰۱" if p < 0.001 else fa(p, 3)


def rows(lines):
    return "\n".join(" & ".join(cells) + r" \\ \hline" for cells in lines) + "\n"


def source_table(combined):
    out = []
    for source, text in SOURCE_FA.items():
        pairs = [r for r in combined if source in r["sources"].split("+")]
        out.append([text, fa(len({r["file"] for r in pairs})), fa(len(pairs)),
                    fa(sum(r["label"] == "1" for r in pairs))])
    out.append([r"\textbf{کل مجموعه‌داده}", fa(len({r["file"] for r in combined})), fa(len(combined)),
                fa(sum(r["label"] == "1" for r in combined))])
    return rows(out)


def type_table(summary, mapping):
    out = []
    for vtype, name in TYPE_FA.items():
        counts = summary["dataset"]["pairs_by_type"][vtype]
        detectors = "، ".join(DETECTOR_FA[d] for d in DETECTOR_FA if d in mapping[vtype]) or "—"
        out.append([name, fa(counts["n"]), fa(counts["positive"]), detectors])
    return rows(out)


def overall_table(summary, view):
    out = []
    for tool in TOOLS:
        m = summary["views"][view]["overall"][tool]
        out.append([TOOL_FA[tool], fa(m["tp"]), fa(m["fp"]), fa(m["fn"]), fa(m["tn"]), fa(m["precision"]),
                    fa(m["recall"]), fa(m["f1"]), fa(m["accuracy"])])
    return rows(out)


def ci_table(summary):
    out = []
    for tool in ("extended", "slither"):
        m = summary["views"]["findings"]["overall"][tool]
        (plo, phi), (rlo, rhi) = m["precision_ci"], m["recall_ci"]
        out.append([TOOL_FA[tool], f"{fa(plo)} تا {fa(phi)}", f"{fa(rlo)} تا {fa(rhi)}"])
    return rows(out)


def bytype_table(summary):
    out = []
    for vtype in TYPES:
        e = summary["views"]["findings"]["by_type"][vtype]
        counts = summary["dataset"]["pairs_by_type"][vtype]
        out.append([TYPE_FA[vtype], fa(counts["n"]), fa(counts["positive"]),
                    fa(e["extended"]["precision"]), fa(e["extended"]["recall"]), fa(e["extended"]["f1"]),
                    fa(e["slither"]["precision"]), fa(e["slither"]["recall"]), fa(e["slither"]["f1"]),
                    fa(e["stock"]["f1"])])
    return rows(out)


def bytype_all_table(summary):
    out = []
    for vtype in TYPES:
        e = summary["views"]["all"]["by_type"][vtype]
        out.append([TYPE_FA[vtype]] + [fa(e[t]["f1"]) for t in TOOLS])
    m = summary["views"]["all"]["overall"]
    out.append([r"\textbf{کل مجموعه‌داده}"] + [fa(m[t]["f1"]) for t in TOOLS])
    return rows(out)


def mcnemar_table(summary):
    view_fa = {"findings": "یافته‌های آسیب‌پذیری", "all": "همۀ خروجی‌ها"}
    out = []
    for view in ("findings", "all"):
        for other in ("stock", "slither"):
            test = summary["views"][view]["mcnemar"][f"extended_vs_{other}"]
            a, p = test["all_pairs"], test["positive_pairs"]
            out.append([view_fa[view], TOOL_FA[other], fa(a["a_only_correct"]), fa(a["b_only_correct"]),
                        fa_p(a["p_value"]), fa(p["a_only_correct"]), fa(p["b_only_correct"]), fa_p(p["p_value"])])
    return rows(out)


def mcnemar_type_table(summary):
    """Findings view, positive pairs of each type: detected only by the extended build vs only by the other."""
    out = []
    for vtype in TYPES:
        tests = summary["views"]["findings"]["mcnemar_by_type"][vtype]
        cells = [TYPE_FA[vtype], fa(summary["dataset"]["pairs_by_type"][vtype]["positive"])]
        for other in ("stock", "slither"):
            p = tests[f"extended_vs_{other}"]["positive_pairs"]
            cells += [fa(p["a_only_correct"]), fa(p["b_only_correct"]), fa_p(p["p_value"])]
        out.append(cells)
    return rows(out)


def detector_table(summary, mapping):
    out = []
    for det, name in DETECTOR_FA.items():
        m = summary["per_detector"][det]
        types = "، ".join(TYPE_FA[t] for t in TYPES if det in mapping[t]) or "—"
        out.append([name, fa(m["contracts_flagged"]), types, fa(m["precision"]), fa(m["recall"])])
    return rows(out)


def chart_data(summary):
    lines = ["type ext slither stock"]
    for i, vtype in enumerate(TYPES, 1):
        e = summary["views"]["findings"]["by_type"][vtype]
        lines.append(f"{i} " + " ".join(f"{e[t]['f1']:.3f}" for t in ("extended", "slither", "stock")))
    return "\n".join(lines) + "\n"


def large_tables(large, labelled_runtime):
    chains = [c for c in CHAIN_FA if c in large]
    out = []
    for chain in chains + ["total"]:
        e = large[chain]
        name = r"\textbf{مجموع}" if chain == "total" else CHAIN_FA[chain]
        share = e["flagged_any_of_six"] / e["analysed"]["extended"] if e["analysed"]["extended"] else float("nan")
        out.append([name, fa(e["files"]), fa(e["analysed"]["extended"]), fa(e["flagged_any_of_six"]),
                    fa(100 * share, 1)])
    t = large["total"]
    per_det = []
    for det, name in DETECTOR_FA.items():
        per_det.append([name] + [fa(large[c]["per_detector"].get(det, 0)) for c in chains]
                       + [fa(t["per_detector"].get(det, 0))])
    runtime = []
    for tool in TOOLS:
        lab = labelled_runtime[tool]
        big = t["runtime_seconds"].get(tool)
        runtime.append([TOOL_FA[tool], fa(lab["median"]), fa(lab["mean"]),
                        fa(big["median"]) if big else "—", fa(big["mean"]) if big else "—"])
    return rows(out), rows(per_det), rows(runtime)


def labelled_runtime(run, combined):
    """Seconds per analysed contract of each tool on the evaluation dataset (all ran one after another)."""
    import statistics
    files = sorted({r["file"] for r in combined})
    out = {}
    for tool in TOOLS:
        data = json.loads((run / f"{tool}.json").read_text())
        seconds = [data[f]["seconds"] for f in files if "findings" in data.get(f, {})]
        out[tool] = {"median": statistics.median(seconds), "mean": statistics.mean(seconds)}
    return out


def chart_overall(summary):
    """Main-view precision, recall and F1 of the three tools (data of the overall chart)."""
    lines = ["metric ext slither stock"]
    for i, key in enumerate(("precision", "recall", "f1"), 1):
        vals = []
        for tool in ("extended", "slither", "stock"):
            v = summary["views"]["findings"]["overall"][tool][key]
            vals.append(0.0 if isinstance(v, float) and math.isnan(v) else v)
        lines.append(f"{i} " + " ".join(f"{v:.3f}" for v in vals))
    return "\n".join(lines) + "\n"


def missed_table(run, summary):
    """Missed vulnerable pairs of the extended build per type: contract not analysed vs analysed."""
    per_row = list(csv.DictReader((run / "datasets_per_row.csv").open()))
    extended = json.loads((run / "extended.json").read_text())
    out = []
    for vtype in TYPES:
        missed = [r for r in per_row if r["type"] == vtype and r["label"] == "1" and r["extended"] == "0"]
        failed = sum("error" in extended.get(r["file"], {"error": 1}) for r in missed)
        out.append([TYPE_FA[vtype], fa(summary["dataset"]["pairs_by_type"][vtype]["positive"]), fa(len(missed)),
                    fa(failed), fa(len(missed) - failed)])
    return rows(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--large", type=Path)
    ap.add_argument("--combined", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    from score_datasets import TYPE_DETECTORS

    summary = json.loads((args.run / "datasets_summary.json").read_text())
    combined = list(csv.DictReader(args.combined.open()))
    tables = {
        "dataset-sources.tex": source_table(combined),
        "dataset-types.tex": type_table(summary, TYPE_DETECTORS),
        "overall-findings.tex": overall_table(summary, "findings"),
        "overall-all.tex": overall_table(summary, "all"),
        "overall-ci.tex": ci_table(summary),
        "bytype.tex": bytype_table(summary),
        "bytype-all.tex": bytype_all_table(summary),
        "mcnemar.tex": mcnemar_table(summary),
        "mcnemar-type.tex": mcnemar_type_table(summary),
        "detectors.tex": detector_table(summary, TYPE_DETECTORS),
        "chart-type.dat": chart_data(summary),
        "chart-overall.dat": chart_overall(summary),
        "missed.tex": missed_table(args.run, summary),
    }
    if args.large and (args.large / "large_summary.json").exists():
        large = json.loads((args.large / "large_summary.json").read_text())
        tables["large.tex"], tables["large-detectors.tex"], tables["large-runtime.tex"] = large_tables(
            large, labelled_runtime(args.run, combined))
        tables["chart-large.dat"] = "detector count\n" + "".join(
            f"{i} {large['total']['per_detector'].get(det, 0)}\n" for i, det in enumerate(DETECTOR_FA, 1))
    for name, text in tables.items():
        (args.out / name).write_text(text, encoding="utf-8")
    print("written:", ", ".join(sorted(tables)))


if __name__ == "__main__":
    main()
