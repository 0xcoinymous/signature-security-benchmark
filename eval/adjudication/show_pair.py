#!/usr/bin/env python3
"""show_pair.py <file> [maxlines]: signature-related functions of a labelled contract and the lines the
extended build reports (run given by RUN, default results/run8)."""
import json, os, re, sys
from pathlib import Path
EVAL = Path(__file__).resolve().parent.parent
BENCH = EVAL.parent.parent / "signature-security-benchmark" / "contracts"
if not BENCH.exists():
    BENCH = Path("/home/a-iraninasab/codes/uni/aderyn/signature-security-benchmark/contracts")
name = sys.argv[1]; maxl = int(sys.argv[2]) if len(sys.argv) > 2 else 45
run = Path(os.environ.get("RUN", EVAL / "results" / "run8"))
lines = (BENCH / name).read_text(errors="ignore").splitlines()
rep = {}
for tool in ("extended", "slither"):
    try:
        r = json.loads((run / f"{tool}.json").read_text()).get(name, {})
    except FileNotFoundError:
        continue
    for f in r.get("findings", []):
        if tool == "slither" and f[0] not in ("encode-packed-collision", "arbitrary-send-erc20-permit", "domain-separator-collision"):
            continue
        if tool == "extended" and f[0] in ("ecrecover",) or len(f) < 2:
            continue
        if tool == "extended" and f[0] not in ("signature-replay", "nonce-management", "eip712-implementation",
                                              "eip1271-verification", "signature-malleability", "signature-freshness"):
            continue
        rep.setdefault(int(f[1]), []).append(f"{tool}:{f[0]}")
# function spans
spans = []
for i, l in enumerate(lines):
    if re.search(r"\bfunction\s+\w+|\bconstructor\s*\(|\bmodifier\s+\w+", l):
        depth, started, j = 0, False, i
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            started |= "{" in lines[j]
            if (started and depth <= 0) or (not started and lines[j].rstrip().endswith(";")):
                break
            j += 1
        spans.append((i, j))
key = re.compile(r"ecrecover|\.recover\(|recover\(|isValidSignature|SignatureChecker|tryRecover|DOMAIN_SEPARATOR|chainid|chainId")
shown = 0
for a, b in spans:
    body = "\n".join(lines[a:b + 1])
    hit = any(a + 1 <= ln <= b + 1 and any(t.startswith("extended") for t in rep[ln]) for ln in rep)
    fname = re.search(r"function\s+(\w+)", lines[a])
    lib = fname and fname.group(1) in ("recover", "tryRecover", "toEthSignedMessageHash", "toTypedDataHash",
                                       "isValidSignatureNow", "_throwError", "verifyCallResult", "_hashTypedDataV4",
                                       "_domainSeparatorV4", "_buildDomainSeparator", "splitSignature")
    if not (hit or (not lib and re.search(r"ecrecover|\.recover\(|recover\(|isValidSignatureNow|SignatureChecker\.", body))):
        continue
    tags = sorted({t for ln, ts in rep.items() if a + 1 <= ln <= b + 1 for t in ts})
    print(f"---- {a+1}-{b+1} {tags}")
    seg = lines[a:b + 1]
    for k, l in enumerate(seg[:maxl]):
        print(f"{a+1+k:5} {l.rstrip()[:150]}")
    if len(seg) > maxl:
        print("      ...")
    shown += 1
    if shown >= 5:
        break
print("chainid in file:", bool(re.search(r"chainid|chainId|getChainId", "\n".join(lines))), "| address(this):", "address(this)" in "\n".join(lines), "| DOMAIN:", "DOMAIN_SEPARATOR" in "\n".join(lines) or "EIP712Domain" in "\n".join(lines))
