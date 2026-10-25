#!/usr/bin/env python3
"""Run one tool on every contract of a dataset, each contract analysed as its own project.

    run_dataset.py aderyn  --bin <aderyn> --contracts DIR --files LIST --out OUT.json [--jobs 8]
    run_dataset.py slither --contracts DIR --files LIST --out OUT.json [--jobs 8]
        [--compilers datasets/compilers.csv --chain Ethereum]

LIST is a text file with one file name per line (relative to DIR). Each contract is copied alone into a
temporary project, so its analysis never depends on the other files of the dataset. The project is
prepared the same way for every tool:
  * a file that holds a standard-JSON compiler input (Etherscan stores multi-file contracts that way)
    is unpacked into its source files, with the remappings it declares;
  * in a concatenated file, every SPDX licence comment after the first is renamed, because solc
    rejects several in one file (comments only, so lines and code are unchanged);
  * the solc version is the one the contract was verified with (from --compilers, keyed by chain and
    the address that starts the file name). Without it, the newest release of each minor series that
    satisfies every `pragma solidity` is tried, newest first, until one compiles.
Aderyn gets the version and remappings through a foundry.toml; Slither compiles a single file with
solc-select and a multi-file project with Foundry.

Output: {file: {"findings": [[detector, line, path], ...]} | {"error": "..."}, with "solc"} plus
OUT.meta.json with timing and versions.
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

PRAGMA_RE = re.compile(r"pragma\s+solidity\s+([^;]+);")
SPDX = "SPDX-License-Identifier"
IMPORT_RE = re.compile(r"^[ \t]*import\s[^;]*;", re.M)
NO_OP_PRAGMA = "pragma solidity >=0.0.0;"
SRC = "x-src"  # source folder of the temporary project; unlikely to clash with a folder of the sources
# Address-space limit of one analysis (and the compiler it starts); a run that exceeds it counts as an error.
LIMIT = ["prlimit", f"--as={4 * 1024 ** 3}", "--"]
TIMEOUT = 900
FALLBACK_TRIES = 4


def all_solc_versions():
    out = subprocess.run(["solc-select", "install"], capture_output=True, text=True).stdout
    versions = re.findall(r"^(\d+\.\d+\.\d+)$", out, re.M)
    installed = subprocess.run(["solc-select", "versions"], capture_output=True, text=True).stdout
    versions += re.findall(r"^(\d+\.\d+\.\d+)", installed, re.M)
    return sorted(set(versions), key=parse)


def parse(v):
    parts = [int(x) for x in re.findall(r"\d+", v)][:3]
    return tuple(parts + [0] * (3 - len(parts)))


def satisfies(version, constraint):
    v = parse(version)
    for alternative in constraint.split("||"):
        ok = True
        for term in alternative.split():
            m = re.match(r"(\^|~|>=|<=|>|<|=)?\s*v?(\d+(?:\.\d+){0,2})", term)
            if not m:
                continue
            op, target = m.group(1) or "=", parse(m.group(2))
            if op == "^":
                upper = (target[0], target[1] + 1, 0) if target[0] == 0 else (target[0] + 1, 0, 0)
                ok &= target <= v < upper
            elif op == "~":
                ok &= target <= v < (target[0], target[1] + 1, 0)
            elif op == ">=":
                ok &= v >= target
            elif op == "<=":
                ok &= v <= target
            elif op == ">":
                ok &= v > target
            elif op == "<":
                ok &= v < target
            else:
                ok &= v == target
        if ok:
            return True
    return False


def single_spdx(text):
    first = text.find(SPDX)
    if first < 0:
        return text
    cut = first + len(SPDX)
    return text[:cut] + text[cut:].replace(SPDX, "SPDX-Licence-Comment")


def without_imports(text):
    """A single file has nothing to import; a concatenated one already contains what its imports name.
    Each import statement becomes a pragma every version accepts (a doc comment above an import would
    otherwise attach to the next contract), keeping the line count."""
    return IMPORT_RE.sub(lambda m: NO_OP_PRAGMA + "\n" * m.group(0).count("\n"), text)


def top_level_items(text):
    """Top-level items of a Solidity file (each with the comments before it) and the trailing text."""
    items, start, depth, i, n = [], 0, 0, 0, len(text)
    while i < n:
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                items.append(text[start:i + 1])
                start = i + 1
        elif c == ";" and depth == 0:
            items.append(text[start:i + 1])
            start = i + 1
        i += 1
    return items, text[start:]


def without_comments(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)


CONTRACT_HEAD_RE = re.compile(r"^(?:abstract\s+)?(?:contract|interface|library)\s+([A-Za-z_$][\w$]*)\s*(?:is\s+(.*))?$",
                              re.S)


def reordered(text):
    """A concatenation of several files rebuilt as one compilable file: pragmas and other file-level
    items first (each distinct pragma once), then every contract after its base contracts. Of two
    definitions with the same name the first is kept."""
    items, tail = top_level_items(text)
    front, contracts, pragmas = [], {}, set()
    for item in items:
        code = without_comments(item).strip()
        head = code.split("{", 1)[0].strip()
        match = CONTRACT_HEAD_RE.match(head) if code.endswith("}") else None
        if match is None:
            if code.startswith("pragma"):
                key = re.sub(r"\s+", " ", code)
                if key in pragmas:
                    continue
                pragmas.add(key)
            front.append(item)
            continue
        name, bases = match.group(1), match.group(2) or ""
        while re.search(r"\([^()]*\)", bases):
            bases = re.sub(r"\([^()]*\)", "", bases)
        bases = [b.split()[0].split(".")[-1] for b in bases.split(",") if b.strip()]
        contracts.setdefault(name, (bases, item))
    ordered, done = [], set()

    def emit(name):
        if name in done:
            return
        done.add(name)
        bases, item = contracts[name]
        for base in bases:
            if base in contracts:
                emit(base)
        ordered.append(item)

    for name in list(contracts):
        emit(name)
    return "".join(front) + "".join(ordered) + tail


def project_sources(path):
    """Variants of the contract stored in `path`, each ({relative path: content}, remappings), in the
    order they are tried: the file as stored, then (for a concatenation) its reordered form."""
    text = path.read_text(errors="replace")
    stripped = text.strip()
    if stripped.startswith("{"):
        if stripped.startswith("{{") and stripped.endswith("}}"):
            stripped = stripped[1:-1]
        try:
            data = json.loads(stripped)
        except ValueError:
            data = None
        if isinstance(data, dict):
            sources = data.get("sources", data)
            files = {}
            for name, source in sources.items():
                rel = PurePosixPath(name)
                if isinstance(source, dict) and "content" in source and not rel.is_absolute() \
                        and ".." not in rel.parts:
                    files[str(rel)] = single_spdx(source["content"])
            if files:
                remappings = [r for r in data.get("settings", {}).get("remappings", [])
                              if isinstance(r, str) and "=" in r and ":" not in r.split("=", 1)[0]]
                return [(files, remappings)]
    stored = without_imports(single_spdx(text))
    variants = [({path.name: stored}, [])]
    rebuilt = reordered(stored)
    if rebuilt != stored:
        variants.append(({path.name: rebuilt}, []))
    return variants


def candidate_versions(files, versions, verified_version):
    if verified_version in versions:
        return [verified_version], "verified"
    constraints = [c.strip() for content in files.values() for c in PRAGMA_RE.findall(content)]
    allowed = [v for v in versions if all(satisfies(v, c) for c in constraints)]
    out, minors = [], set()
    for v in reversed(allowed):
        minor = v.rsplit(".", 1)[0]
        if minor not in minors:
            minors.add(minor)
            out.append(v)
    return out[:FALLBACK_TRIES], "pragma"


def write_project(project, files, remappings, solc):
    for rel, content in files.items():
        target = project / SRC / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    tops = sorted({PurePosixPath(rel).parts[0] for rel in files if len(PurePosixPath(rel).parts) > 1})
    remaps = [f"{a}={SRC}/{b}" for a, b in (r.split("=", 1) for r in remappings)]
    remaps += [f"{top}/={SRC}/{top}/" for top in tops]
    (project / "foundry.toml").write_text(
        f'[profile.default]\nsrc = "{SRC}"\nlibs = []\nsolc_version = "{solc}"\n'
        f"remappings = {json.dumps(remaps)}\n")


def run_aderyn(binary, files, remappings, solc):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        write_project(project, files, remappings, solc)
        out = project / "out.json"
        try:
            proc = subprocess.run([*LIMIT, binary, str(project), "-s", SRC, "-o", str(out)],
                                  capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return {"error": "timeout"}
        if not out.exists():
            return {"error": (proc.stderr or proc.stdout)[-400:]}
        data = json.loads(out.read_text())
    findings = set()
    for key in ("high_issues", "low_issues"):
        for issue in data.get(key, {}).get("issues", []):
            for instance in issue.get("instances", []):
                path = instance.get("contract_path", "").removeprefix(f"{SRC}/")
                findings.add((issue["detector_name"], instance.get("line_no", 0), path))
    return {"findings": sorted(findings)}


def run_slither(files, remappings, solc):
    multi = len(files) > 1
    result = {}
    for extra in ([], ["--solc-args", "--via-ir --optimize"]):
        if multi and extra:
            break
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            out = project / "out.json"
            if multi:
                write_project(project, files, remappings, solc)
                target = ["."]
                compile_args = ["--compile-force-framework", "foundry"]
            else:
                name, content = next(iter(files.items()))
                (project / name).parent.mkdir(parents=True, exist_ok=True)
                (project / name).write_text(content)
                target = [name]
                compile_args = ["--solc-solcs-select", solc, *extra]
            try:
                proc = subprocess.run([*LIMIT, "slither", *target, "--json", str(out), "--disable-color",
                                       *compile_args], cwd=tmp, capture_output=True, text=True,
                                      timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                return {"error": "timeout"}
            data = json.loads(out.read_text()) if out.exists() else None
        if data and data.get("success"):
            checks = set()
            for det in data.get("results", {}).get("detectors", []):
                elements = det.get("elements", [])
                mapping = elements[0].get("source_mapping", {}) if elements else {}
                line = (mapping.get("lines") or [0])[0]
                path = str(mapping.get("filename_relative", "")).removeprefix(f"{SRC}/")
                checks.add((det["check"], line, path))
            return {"findings": sorted(checks)}
        error = str(data.get("error") if data else proc.stderr[-400:])
        result = {"error": error[-400:]}
        if "Stack too deep" not in error:
            break
    return result


def install_for_aderyn(binary, solc):
    """Let Aderyn (and Foundry) install one solc version before the parallel runs share it."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        write_project(project, {"Stub.sol": f"pragma solidity {solc};\ncontract Stub {{}}\n"}, [], solc)
        subprocess.run([binary, str(project), "-s", SRC, "-o", str(project / "out.json")],
                       capture_output=True, timeout=TIMEOUT)


def is_resource_error(result):
    error = result.get("error", "")
    return error == "timeout" or "memory allocation" in error


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tool", choices=["aderyn", "slither"])
    ap.add_argument("--bin")
    ap.add_argument("--installer", help="Aderyn binary used only to install solc versions for Foundry")
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--files", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--compilers")
    ap.add_argument("--chain", default="Ethereum")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()

    root = Path(args.contracts).resolve()
    names = [n.strip() for n in Path(args.files).read_text().splitlines() if n.strip()]
    out_path = Path(args.out)
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [n for n in names if n not in results]
    versions = all_solc_versions()
    verified = {}
    if args.compilers:
        # The given chain first; an address listed only for another chain (a contract from that chain in a
        # mixed folder) falls back to it.
        rows = sorted(csv.DictReader(open(args.compilers)), key=lambda row: row["chain"] == args.chain)
        verified = {row["address"]: row["compiler"] for row in rows}

    sources = {n: project_sources(root / n) for n in todo}
    choice = {n: candidate_versions(sources[n][0][0], versions, verified.get(n.split("_", 1)[0].lower()))
              for n in todo}

    # Install every compiler that may be needed once, sequentially, before the parallel runs.
    needed = sorted({v for candidates, _ in choice.values() for v in candidates}, key=parse)
    installer = args.bin if args.tool == "aderyn" else args.installer
    for version in needed:
        if installer:
            install_for_aderyn(installer, version)
        if args.tool == "slither":
            subprocess.run(["solc-select", "install", version], capture_output=True)

    def work(name):
        started = time.time()
        candidates, origin = choice[name]
        result = {"error": "no solc version satisfies the pragmas"}
        for variant, (files, remappings) in enumerate(sources[name]):
            for solc in candidates:
                if args.tool == "aderyn":
                    result = run_aderyn(args.bin, files, remappings, solc)
                else:
                    result = run_slither(files, remappings, solc)
                result["solc"], result["variant"] = solc, variant
                if "findings" in result or is_resource_error(result):
                    break
            if "findings" in result or is_resource_error(result):
                break
        result["solc_source"] = origin
        result["files"] = len(files)
        result["seconds"] = round(time.time() - started, 2)
        return name, result

    start = time.time()
    with ThreadPoolExecutor(args.jobs) as pool:
        for i, (name, result) in enumerate(pool.map(work, todo), 1):
            results[name] = result
            if i % 10 == 0:
                out_path.write_text(json.dumps(results, indent=0))
                print(f"{i}/{len(todo)} done", flush=True)
    elapsed = time.time() - start
    out_path.write_text(json.dumps(results, indent=0))
    errors = sum(1 for n in names if "error" in results.get(n, {}))
    meta = {"tool": args.tool, "binary": args.bin, "files": len(names), "errors": errors,
            "wall_seconds": round(elapsed, 1), "jobs": args.jobs, "compilers": args.compilers,
            "chain": args.chain}
    if args.tool == "aderyn":
        meta["version"] = subprocess.run([args.bin, "--version"], capture_output=True, text=True).stdout.strip()
    else:
        meta["version"] = subprocess.run(["slither", "--version"], capture_output=True, text=True).stdout.strip()
    out_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1))
    print(f"{args.tool}: {len(names) - errors}/{len(names)} analysed in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
