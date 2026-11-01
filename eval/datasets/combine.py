#!/usr/bin/env python3
"""Build the one evaluation dataset of the thesis from its sources: combined.csv.

    combine.py --large-dir <dir from `fetch.py large`> --contracts ../contracts

Unit: a labelled (contract, vulnerability type) pair, because the sources label different types.
Sources (ids used only in this file and in combined.csv):
  S1  labelled sample of a signature-replay study (labels.csv, dataset D1): replay yes/no per contract
  S2  random sample of a cryptographic-defect study (D2): every signature defect type per contract
  S3  reports of that study's analyser, confirmed or rejected by hand (D3)
  S4  audited and widely used contracts (../realworld/cases.json)
  S5  contracts the replay study confirmed exploitable by on-chain simulation (raw/lasir/RQ1_Manual_analysis.csv)
A pair listed by several sources is kept once; it is positive if any source marks it positive, and a
disagreement is flagged. S5 contracts that are not yet in the benchmark folder are copied there from the
large set (official names, lower-case address).
"""
import argparse
import csv
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TYPE_OF = {
    "signature_replay": "replay",
    "Single_Contract_Signature_Replay": "replay_single",
    "Cross_Contract_Signature_Replay": "replay_cross_contract",
    "Cross_Chain_Signature_Replay": "replay_cross_chain",
    "Signature_Malleability": "malleability",
    "Insufficient_Signature_Verification": "insufficient_verification",
    "Signature_Frontrunning": "frontrunning",
}
SOURCE_OF = {"D1": "S1", "D2": "S2", "D3": "S3"}
CHAINS = ["Ethereum", "BSC", "Polygon", "Arbitrum"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--large-dir", required=True)
    ap.add_argument("--contracts", required=True)
    args = ap.parse_args()
    contracts = Path(args.contracts)
    pairs = {}

    def add(file_name, chain, vtype, label, source):
        key = (file_name, vtype)
        if key in pairs:
            entry = pairs[key]
            entry["conflict"] = int(entry["conflict"] or entry["label"] != label)
            entry["label"] = max(entry["label"], label)
            entry["sources"] = "+".join(sorted(set(entry["sources"].split("+")) | {source}))
        else:
            pairs[key] = {"file": file_name, "chain": chain, "type": vtype, "label": label,
                          "sources": source, "conflict": 0}

    for row in csv.DictReader(open(HERE / "labels.csv")):
        add(row["file"], "Ethereum", TYPE_OF[row["defect"]], int(row["label"]), SOURCE_OF[row["dataset"]])

    for case in json.loads((HERE.parent / "realworld" / "cases.json").read_text()):
        if case["scope"] != "in":
            continue
        if case["family"] == "SM":
            vtype = "malleability"
        elif case["family"] == "SR":
            vtype = "replay"
        elif case["label"] == 1:
            vtype = "insufficient_verification"  # the audit finding is SWC-122
        else:
            vtype = "replay"  # widely used code without known findings: not replayable
        add(case["bench_file"], "Ethereum", vtype, int(case["label"]), "S4")

    confirmed = {(row["Blockchain"].strip(), row["Address"].strip().lower())
                 for row in csv.DictReader(open(HERE / "raw" / "lasir" / "RQ1_Manual_analysis.csv",
                                                encoding="utf-8-sig"))}
    present = {p.name.split("_", 1)[0].lower(): p.name for p in contracts.glob("0x*.sol")}
    copied = 0
    for chain, address in sorted(confirmed):
        if address in present:
            name = present[address]
        else:
            names = [n for n in (HERE.parent / "results" / "run9" / f"files_{chain}.txt").read_text().split()
                     if n.split("_", 1)[0].lower() == address]
            source = Path(args.large_dir) / chain / names[0]
            name = f"{address}_{names[0].split('_', 1)[1]}"
            shutil.copy(source, contracts / name)
            present[address] = name
            copied += 1
        add(name, chain, "replay", 1, "S5")

    rows = sorted(pairs.values(), key=lambda r: (r["file"], r["type"]))
    with open(HERE / "combined.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "chain", "type", "label", "sources", "conflict"])
        writer.writeheader()
        writer.writerows(rows)
    files = sorted({r["file"] for r in rows})
    print(f"pairs {len(rows)}, positive {sum(r['label'] for r in rows)}, contracts {len(files)}, "
          f"conflicts {sum(r['conflict'] for r in rows)}, copied {copied}")


if __name__ == "__main__":
    main()
