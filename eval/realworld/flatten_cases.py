#!/usr/bin/env python3
"""Flatten each built real-world case into one self-contained .sol file in the benchmark folder.

Uses `forge flatten` (all imports inlined, as on Etherscan). The output name comes from the case's
"bench_file" field; cases that share a file (two findings in one contract) are flattened once.

Usage:
  flatten_cases.py --cases cases.json --dir cases/ --out <benchmark>/contracts
"""
import argparse
import json
import re
import subprocess
from pathlib import Path


def restore_slot_references(text, case_dir):
    """Undo a forge 0.3.0 flatten bug: inline-assembly `name_slot` is rewritten to `Contract.name`.

    Only names that appear as `<name>_slot` in the original sources are restored.
    """
    slot_names = set()
    for sol in case_dir.rglob("*.sol"):
        slot_names |= set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)_slot\b", sol.read_text(errors="ignore")))
    if not slot_names:
        return text
    pattern = re.compile(r"\b[A-Z][A-Za-z0-9_]*\.(" + "|".join(map(re.escape, slot_names)) + r")\b(?!\s*\()")
    return pattern.sub(lambda m: f"{m.group(1)}_slot", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out).resolve()
    done = set()
    for case in json.loads(Path(args.cases).read_text()):
        if case.get("scope") != "in" or case["bench_file"] in done:
            continue
        case_dir = (Path(args.dir) / case["id"]).resolve()
        target = out / case["bench_file"]
        subprocess.run(
            ["forge", "flatten", "--root", ".", "--contracts", "src",
             str(Path("src") / case["file"]), "-o", str(target)],
            cwd=case_dir, check=True, capture_output=True, text=True,
        )
        header = (
            f"// Real-world case: {case['id']}\n"
            f"// Source: {case.get('repo_url', '')}\n"
            f"// Flattened with `forge flatten`; original file: {case['file']}\n"
        )
        text = restore_slot_references(target.read_text(), case_dir)
        target.write_text(header + text)
        done.add(case["bench_file"])
        print(f"{case['bench_file']}: {sum(1 for _ in target.open())} lines")


if __name__ == "__main__":
    main()
