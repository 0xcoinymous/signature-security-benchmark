#!/usr/bin/env python3
"""Build the real-contract evaluation datasets from the artifacts of two published studies.

    fetch.py labelled --cryptoscan-repo <partial clone> --out <contracts dir>   # D1, D2, D3
    fetch.py large --out <dir>                                                 # D5 (15,383 files)
    fetch.py compilers --meta-dir <cache dir>                                  # compilers.csv

D1  LASiR (ICSE 2026) DB2: 500 random real Ethereum contracts, 72 signature-replay positive / 428 negative.
    Labels: anonymous.4open.science/r/LASiR-B207 Dataset/RQ2/Labeled_Data.csv (copied to raw/lasir/).
D2  CryptoScan (TSE 2025) Experiments/Dataset2: 96 random real Ethereum contracts, every defect type annotated.
D3  CryptoScan Experiments/Dataset1: contracts CryptoScan reported for each defect type, manually labelled TP/FP.
D5  LASiR DB1: the 15,383 contracts that call ecrecover on Ethereum, BSC, Polygon and Arbitrum (no labels).

Sources: D1 and D5 from the tintinweb smart-contract-sanctuary mirrors at the commits LASiR lists; D2 and D3
from CryptoScan's Dataset/SourceCode. Every file is saved as `<address>_<ContractName>.sol` (official
contract name from the verified source). Labels go to labels.csv, provenance to sources.csv.
"""
import argparse
import csv
import io
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

SANCTUARY = {
    "Ethereum": ("smart-contract-sanctuary-ethereum", "015d0105102504dc8733a18c3543f87f1829a5e8"),
    "BSC": ("smart-contract-sanctuary-bsc", "74cf9ca766e80dc7fc2af7aee4ff6d896002b636"),
    "Polygon": ("smart-contract-sanctuary-polygon", "5e5bbae191cb03ae7ea58c80219e44edfb938a1d"),
    "Arbitrum": ("smart-contract-sanctuary-arbitrum", "465b14914e025d2892dd0b484ef8bf8b1efbefe3"),
}

CRYPTOSCAN = ("Jiashuo-Zhang/CryptoScan", "257913106fde079dda2e99cd91c9a82c0b16bc75")

# CryptoScan defect types used here (Dataset1 file stem -> Dataset2 column).
CRYPTOSCAN_TYPES = {
    "Single_Contract_Signature_Replay": "Inter-Contract Signature Replay",
    "Cross_Contract_Signature_Replay": "Cross-Contract Signature Replay",
    "Cross_Chain_Signature_Replay": "Cross-Chain Signature Replay",
    "Signature_Malleability": "Signature Malleability",
    "Insufficient_Signature_Verification": "Insufficient Signature Verification",
    "Signature_Frontrunning": "Front-Running Signature Replay",
}


def sanctuary_url(chain: str, file_name: str) -> str:
    repo, commit = SANCTUARY[chain]
    stem = file_name[2:] if file_name.lower().startswith("0x") else file_name
    return (f"https://raw.githubusercontent.com/tintinweb/{repo}/{commit}/contracts/mainnet/"
            f"{stem[:2].lower()}/{stem}")


def cryptoscan_url(path: str) -> str:
    repo, commit = CRYPTOSCAN
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path)}"


def download(url: str) -> bytes | None:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def git_show(repo: Path, path: str) -> str:
    """A file of the CryptoScan repository at the pinned commit (labels are read from a local clone)."""
    return subprocess.run(["git", "-C", str(repo), "show", f"{CRYPTOSCAN[1]}:{path}"], check=True,
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def labelled(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(args.cryptoscan_repo)
    labels, sources = [], {}

    # D1: LASiR DB2 (all in the Ethereum list of DB1). Its 500 rows hold 470 distinct contracts: 30 are
    # listed twice with the same label, and each contract is kept once.
    for row in csv.reader(open(RAW / "lasir" / "DB2_Labeled_Data.csv", encoding="utf-8-sig")):
        if not row:
            continue
        label, name = row[0].strip(), row[1].strip()
        address = name.split("_", 1)[0].lower()
        file_name = f"{address}_{name.split('_', 1)[1]}"
        if file_name in sources:
            continue
        labels.append({"file": file_name, "dataset": "D1", "address": address, "defect": "signature_replay",
                       "label": int(label == "positive")})
        sources[file_name] = ("sanctuary-ethereum", sanctuary_url("Ethereum", name))

    # CryptoScan source names: <Name>_<address>.sol
    listing = subprocess.run(["git", "-C", str(repo), "ls-tree", "--name-only", CRYPTOSCAN[1], "Dataset/SourceCode/"],
                             check=True, capture_output=True, text=True).stdout.split("\n")
    by_address = {}
    for path in listing:
        stem = path.rsplit("/", 1)[-1]
        if stem.endswith(".sol") and "_0x" in stem:
            name, address = stem[:-4].rsplit("_", 1)
            by_address.setdefault(address.lower(), (name, path))

    def cryptoscan_file(address: str):
        entry = by_address.get(address.lower())
        if not entry:
            return None
        name, path = entry
        file_name = f"{address.lower()}_{name}.sol"
        sources.setdefault(file_name, ("cryptoscan", cryptoscan_url(path)))
        return file_name

    # D2: CryptoScan Dataset2 (cell = CryptoScan's outcome: TP/FN -> defect present).
    rows = list(csv.reader(io.StringIO(git_show(repo, "Experiments/Dataset2/Dataset2.csv"))))
    header = rows[0]
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        file_name = cryptoscan_file(row[0].strip())
        if not file_name:
            print("D2 missing source:", row[0], file=sys.stderr)
            continue
        for stem, column in CRYPTOSCAN_TYPES.items():
            cell = row[header.index(column)].strip() if column in header else ""
            labels.append({"file": file_name, "dataset": "D2", "address": row[0].strip().lower(),
                           "defect": stem, "label": int(cell in ("TP", "FN")),
                           "cryptoscan": int(cell in ("TP", "FP"))})

    # D3: CryptoScan Dataset1 (every row was reported by CryptoScan; TP/FP is the manual label). A contract
    # listed more than once for a type is kept once; it counts as positive if any of its rows is TP.
    d3 = {}
    for stem in CRYPTOSCAN_TYPES:
        text = git_show(repo, f"Experiments/Dataset1/{stem}.csv")
        for row in list(csv.reader(io.StringIO(text)))[1:]:
            if len(row) < 2 or not row[0].strip().lower().startswith("0x"):
                continue
            verdict = row[1].strip().upper()
            if verdict not in ("TP", "FP", "T", "F"):
                continue
            file_name = cryptoscan_file(row[0].strip())
            if not file_name:
                print("D3 missing source:", row[0], file=sys.stderr)
                continue
            key = (file_name, stem)
            positive = int(verdict in ("TP", "T")) or d3.get(key, {"label": 0})["label"]
            d3[key] = {"file": file_name, "dataset": "D3", "address": row[0].strip().lower(),
                       "defect": stem, "label": positive, "cryptoscan": 1}
    labels.extend(d3.values())

    fields = ["file", "dataset", "address", "defect", "label", "cryptoscan"]
    with open(HERE / "labels.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(labels)
    with open(HERE / "sources.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "origin", "url"])
        for file_name, (kind, url) in sorted(sources.items()):
            writer.writerow([file_name, kind, url])

    todo = {f: u for f, (_, u) in sources.items() if not (out / f).exists()}
    with ThreadPoolExecutor(8) as pool:
        for file_name, data in zip(todo, pool.map(download, todo.values())):
            if data is None:
                print("download failed:", file_name, todo[file_name], file=sys.stderr)
            else:
                (out / file_name).write_bytes(data)
    present = sum(1 for f in sources if (out / f).exists())
    print(f"labels: {len(labels)} rows, files: {len(sources)} ({present} present)")


def compilers(args) -> None:
    """compilers.csv: the compiler each contract was verified with, from the contracts.json index of the
    sanctuary mirror of its chain (at the pinned commit)."""
    meta = Path(args.meta_dir)
    meta.mkdir(parents=True, exist_ok=True)
    wanted = {chain: set() for chain in SANCTUARY}
    for row in csv.DictReader(open(HERE / "labels.csv")):
        wanted["Ethereum"].add(row["address"].lower())
    for chain in SANCTUARY:
        for line in open(RAW / "lasir" / f"DB1_{chain}.csv", encoding="utf-8-sig"):
            name = line.strip().strip(",")
            if name:
                wanted[chain].add(name.split("_", 1)[0].lower())
    rows = []
    for chain, (repo, commit) in SANCTUARY.items():
        index = meta / f"{chain.lower()}.json"
        if not index.exists():
            data = download(f"https://raw.githubusercontent.com/tintinweb/{repo}/{commit}/contracts/mainnet/contracts.json")
            if data is None:
                sys.exit(f"cannot download the contracts.json of {chain}")
            index.write_bytes(data)
        found = {}
        for line in open(index, encoding="utf-8", errors="replace"):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            address = str(entry.get("address", "")).lower()
            version = re.search(r"(\d+\.\d+\.\d+)", str(entry.get("compiler", "")))
            if address in wanted[chain] and address not in found and version:
                found[address] = version.group(1)
        rows += [(chain, address, found[address]) for address in sorted(found)]
        print(f"{chain}: compiler known for {len(found)} of {len(wanted[chain])} addresses")
    with open(HERE / "compilers.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["chain", "address", "compiler"])
        writer.writerows(rows)


def large(args) -> None:
    out = Path(args.out)
    jobs = []
    for chain in SANCTUARY:
        for line in open(RAW / "lasir" / f"DB1_{chain}.csv", encoding="utf-8-sig"):
            name = line.strip().strip(",")
            if name:
                target = out / chain / name
                if not target.exists():
                    jobs.append((target, sanctuary_url(chain, name)))
    for chain in SANCTUARY:
        (out / chain).mkdir(parents=True, exist_ok=True)
    failed = 0
    with ThreadPoolExecutor(16) as pool:
        for (target, _), data in zip(jobs, pool.map(lambda j: download(j[1]), jobs)):
            if data is None:
                failed += 1
            else:
                target.write_bytes(data)
    print(f"requested {len(jobs)}, failed {failed}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("labelled")
    p.add_argument("--cryptoscan-repo", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=labelled)
    p = sub.add_parser("compilers")
    p.add_argument("--meta-dir", required=True)
    p.set_defaults(func=compilers)
    p = sub.add_parser("large")
    p.add_argument("--out", required=True)
    p.set_defaults(func=large)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
