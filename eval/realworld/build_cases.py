#!/usr/bin/env python3
"""Assemble real-world cases as small self-contained Solidity projects.

For each case in cases.json:
  - copy the audited file and its local (relative) import tree from a DAppSCAN checkout
    (source "dappscan"), or download them from a GitHub repository at a pinned commit
    (source "github", case["raw"] = raw-content base URL),
  - download every non-relative import from the dependency's official GitHub release at the
    version pinned by the project's package.json, recursively,
  - lay everything out under <out>/<case>/ so that import paths resolve unchanged
    (local tree under src/, packages under node_modules/<package>/).

Usage:
  build_cases.py --cases cases.json --dappscan DAppSCAN-source/contracts --out cases/
"""
import argparse
import json
import os
import re
import shutil
import urllib.request
from pathlib import Path

IMPORT_RE = re.compile(r'import\s+(?:[^"\']*from\s+)?["\']([^"\']+)["\']')


def fetch(url, cache):
    if url in cache:
        return cache[url]
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = resp.read().decode("utf8")
    cache[url] = text
    return text


def package_for(import_path, packages):
    """Longest matching package prefix -> (prefix, spec)."""
    best = None
    for prefix, spec in packages.items():
        if import_path.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, spec)
    return best


def build_case(case, dappscan, out, cache):
    case_dir = out / case["id"]
    if case_dir.exists():
        shutil.rmtree(case_dir)
    packages = case.get("packages", {})
    remote = case["source"] == "github"
    if remote:
        # Repository files are addressed by their path inside the repo, fetched from case["raw"].
        root_file = Path(case["file"])
    else:
        src_root = dappscan / case["project_dir"]
        root_file = src_root / case["file"]

    pending = [("local", root_file)]
    seen = set()
    while pending:
        kind, item = pending.pop()
        if (kind, str(item)) in seen:
            continue
        seen.add((kind, str(item)))

        if kind == "local" and remote:
            dest = case_dir / "src" / item
            text = fetch(case["raw"].rstrip("/") + "/" + item.as_posix(), cache)
            base_dir = item.parent
        elif kind == "local":
            rel = item.relative_to(src_root)
            dest = case_dir / "src" / rel
            text = item.read_text(encoding="utf8", errors="ignore")
            base_dir = item.parent
        else:  # external package file, item = import path like @openzeppelin/contracts/x.sol
            prefix, spec = package_for(item, packages)
            url = spec["raw"].rstrip("/") + "/" + item[len(prefix):]
            text = fetch(url, cache)
            dest = case_dir / "node_modules" / item
            base_dir = None

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf8")

        for imp in IMPORT_RE.findall(text):
            if imp.startswith("."):
                if kind == "local":
                    pending.append(("local", Path(os.path.normpath(base_dir / imp))))
                else:
                    pending.append(("ext", os.path.normpath(os.path.join(os.path.dirname(item), imp))))
            else:
                if package_for(imp, packages) is None:
                    raise SystemExit(f"{case['id']}: no package mapping for import {imp}")
                pending.append(("ext", imp))

    # Remappings so tools resolve package imports to node_modules/.
    remaps = sorted({f"{p}=node_modules/{p}" for p in packages})
    (case_dir / "remappings.txt").write_text("\n".join(remaps) + ("\n" if remaps else ""))
    n_files = sum(1 for _ in case_dir.rglob("*.sol"))
    return n_files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--dappscan", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cases = json.loads(Path(args.cases).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = {}
    for case in cases:
        if case.get("scope") != "in":
            continue
        n = build_case(case, Path(args.dappscan), out, cache)
        print(f"{case['id']}: {n} .sol files")


if __name__ == "__main__":
    main()
