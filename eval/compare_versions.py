#!/usr/bin/env python3
"""Check that the expansion bound of thesis-eval-v3.1 changes no result of thesis-eval-v3.

    compare_versions.py --old results/run4/extended_v3.json --new results/run4/extended.json

For every file both builds analysed, the findings of the six detectors must be identical; files only
v3.1 analysed are those v3 could not finish.
"""
import argparse
import json
from pathlib import Path

from score_datasets import SIX


def six(result):
    return sorted(tuple(f) for f in result.get("findings", []) if f[0] in SIX)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    args = ap.parse_args()
    old = json.loads(Path(args.old).read_text())
    new = json.loads(Path(args.new).read_text())
    both = [n for n in new if "findings" in new[n] and "findings" in old.get(n, {})]
    differ = [n for n in both if six(old[n]) != six(new[n])]
    only_new = [n for n in new if "findings" in new[n] and "findings" not in old.get(n, {})]
    only_old = [n for n in old if "findings" in old[n] and "findings" not in new.get(n, {})]
    print(f"analysed by both: {len(both)}, identical: {len(both) - len(differ)}, different: {len(differ)}")
    print(f"analysed only by v3.1: {len(only_new)}, only by v3: {len(only_old)}")
    for n in only_new:
        print("  v3 error:", n, old.get(n, {}).get("error", "")[-80:].replace("\n", " "))
    for n in differ:
        print("  differs:", n)


if __name__ == "__main__":
    main()
