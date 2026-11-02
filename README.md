# Signature Security Benchmark

Real Solidity contracts with labelled signature-related vulnerabilities, together with the scripts and raw
results used to evaluate six static detectors for Aderyn against stock Aderyn and Slither.

This repository accompanies the article *Static Detection of Signature-Related Vulnerabilities in Smart
Contracts: Six Detectors for Aderyn and an Evaluation on Real-World Contracts* by Abolfazl Iraninasab and
Farzan Haddadi (Iran University of Science and Technology; under review). The detectors themselves are in
the Aderyn fork at <https://github.com/0xcoinymous/aderyn/tree/cryptography_hooks>; the results below were
produced with commit `be23052e` of that branch.

## Contents

```
contracts/                 1,099 verified contract sources (one file per contract)
eval/
  datasets/                labels, provenance, compiler versions and the scripts that build them
  realworld/               the audited and widely used contracts (source S4) and how they were built
  examples/                one vulnerable and one fixed example per detector family
  results/run8/            raw outputs and scores of the three tools on the labelled dataset
  results/run9/            raw outputs of the two Aderyn builds on 15,353 deployed contracts
  adjudication/            the review of the pairs labelled safe that a tool reports (criteria and verdicts)
  manual_review/           a hand review of 30 random findings of four detectors
  *.py, *.sh               scripts to run the tools, score them and produce the article's tables
```

## Dataset

The labelled dataset has **1,099 contracts and 1,629 labelled (contract, vulnerability type) pairs**,
combined from five sources. Every contract is real, deployed code with verified source.

| Source | Contracts | Pairs | Origin |
|---|---:|---:|---|
| S1 | 470 | 470 | random sample of Ethereum contracts that use `ecrecover`, labelled for signature replay [1] |
| S2 | 92 | 552 | random sample of cryptography-related contracts, every signature defect type labelled [2] |
| S3 | 504 | 564 | signature defects reported by an analyser and confirmed or rejected by hand [2] |
| S4 | 18 | 18 | contracts with audit-confirmed weaknesses [3] and widely used contracts without known findings |
| S5 | 29 | 29 | contracts whose replay exploitation was confirmed by on-chain simulation [1] |

Contracts listed twice in S1 were kept once, pairs present in two sources were merged, and no two sources
disagree on a pair. The labels were mapped to seven types; the five types targeted by the detectors are
scored (1,259 pairs; 492 vulnerable by the source labels, 570 after the label review below):

| Type | Pairs | Vulnerable (sources) | Vulnerable (reviewed) |
|---|---:|---:|---:|
| Signature replay (general) | 510 | 100 | 173 |
| Replay within a contract | 184 | 80 | 85 |
| Cross-contract replay | 186 | 102 | 102 |
| Cross-chain replay | 188 | 105 | 105 |
| Signature malleability | 191 | 105 | 105 |
| Insufficient verification (not scored) | 184 | 91 | – |
| Signature front-running (not scored) | 186 | 92 | – |

### Label review

The sources label a pair vulnerable by their own definition; for replay, only when the replay is
exploitable in practice. This study counts every signature weakness, whether or not funds can be taken.
Every scored pair labelled 0 that one of the three tools reports in the findings view (219 pairs) was
therefore re-examined by reading the code against the written criteria in `eval/adjudication/CRITERIA.md`.
78 pairs have the weakness of their type under that definition and are counted as vulnerable, most often a
signature that can be used again (an allow-list pass limited only by a per-wallet cap) or a signed message
bound neither to the contract nor to the chain; the other 141 keep their label.
`eval/adjudication/adjudication.csv` lists every reviewed pair with its source label, the label used and a
one-line reason, and `score_datasets.py` applies it. Pairs labelled safe that no tool reports were not
reviewed, which can overstate recall.

### Files

- `contracts/<address>_<ContractName>.sol`: sources from published studies (address in lower case);
  `contracts/<Project>_<File>.sol`: the S4 contracts, flattened into one file each.
- `eval/datasets/combined.csv` (`file,chain,type,label,sources,conflict`): the evaluation dataset, one row
  per pair; `label` is 1 for vulnerable, `sources` lists S1–S5.
- `eval/datasets/labels.csv`: the labels as read from the source studies, before combining.
- `eval/datasets/sources.csv` (`file,origin,url`): where each contract source was downloaded from.
- `eval/datasets/compilers.csv` (`chain,address,compiler`): the compiler version each contract was
  verified with.
- `eval/datasets/raw/lasir/`: the label files of [1] as published in its artifact.
- `eval/realworld/cases.json`: the S4 cases with their audits, repositories and pinned commits.

## Results

- `eval/results/run8/{extended,stock,slither}.json`: findings and time per contract of each tool;
  `datasets_summary.json` and `datasets_per_row.csv`: the scores.
- `eval/results/run9/<Chain>_extended.json` and `Ethereum_stock.json`: the run on 15,353 deployed contracts on
  Ethereum, BNB Smart Chain, Polygon and Arbitrum (address lists in `files_<Chain>.txt`; the sources are not
  stored here and are downloaded with `eval/datasets/fetch.py large`); `large_summary.json`: counts and
  runtime.

Counting what each tool reports as a vulnerability, on the 1,259 scored pairs:

| Tool | P | R | F1 | Accuracy |
|---|---:|---:|---:|---:|
| Extended Aderyn | 0.85 | 0.77 | 0.81 | 0.83 |
| Stock Aderyn | – | 0.00 | 0.00 | 0.55 |
| Slither | 0.61 | 0.18 | 0.27 | 0.58 |

Times per contract (`seconds` in the result files) include compilation; Aderyn ran with
`--skip-update-check`, so that its time does not include the request for its newest release that it otherwise
sends to GitHub on every run, and all runs were made on one laptop on mains power (`results/run9/power.log`).
The median was 0.15 s for the extended build, 0.14 s for stock Aderyn and 0.92 s for Slither on the labelled
dataset, and 0.24 s for both Aderyn builds on the deployed Ethereum contracts.

### Manual review

`eval/manual_review/` holds 30 random findings of each of four detectors (seed 1404, drawn by `sample.py`
from run8 and run9; the ERC-1271 detector reported in none of these contracts), each with a verdict and a one-line reason, the criteria in `CRITERIA.md`, and
`table.py`, which computes the precision with a Wilson 95% interval. A finding is a weakness if the reported
function has the weakness the detector's rule describes, whether or not it is exploitable.

| Detector | Weaknesses | Precision [95% CI] |
|---|---:|---|
| signature-malleability | 30/30 | 1.00 [0.89, 1.00] |
| eip712-implementation | 17/30 | 0.57 [0.39, 0.73] |
| signature-freshness | 14/30 | 0.47 [0.30, 0.64] |
| nonce-management | 9/30 | 0.30 [0.17, 0.48] |

## Reproducing

Requirements: Python 3 with `scipy`, Slither 0.11.6, solc versions as listed in `compilers.csv`, and two
Aderyn builds: the extended one from commit `be23052e` of the fork (`cargo build --release`) and stock
Aderyn 0.6.8.

```bash
cd eval
python3 datasets/fetch.py large --out <large dir>          # the deployed contracts
./run_final.sh <extended aderyn> <stock aderyn> <large dir>  # writes results/run8 and results/run9
python3 score_datasets.py --combined datasets/combined.csv --run results/run8 --out results/run8
python3 score_large.py --runs results/run9 --lasir-dir datasets/raw/lasir --out results/run9
python3 make_paper_tables.py --run results/run8 --large results/run9 \
    --combined datasets/combined.csv --out <tables dir>
python3 manual_review/table.py --d5-dir <large dir> --thesis <file> --paper <file>
```

`fp_functions.py` lists the functions behind the most frequent false positives, and
`examples/run_examples.sh <aderyn>` runs a build on the worked examples (expected output in
`examples/results.txt`).

## License

The scripts, labels and results are released under the MIT License (see `LICENSE`). The contracts in
`contracts/` and `eval/realworld/cases/` are third-party code published on public blockchains and keep their
original licenses as stated in their SPDX headers. The label files in `eval/datasets/raw/` belong to the
authors of [1].

## References

1. Z. Wang et al., "One Signature, Multiple Payments: Demystifying and Detecting Signature Replay
   Vulnerabilities in Smart Contracts," ICSE 2026. <https://doi.org/10.1145/3744916.3773198>
   (artifact: <https://anonymous.4open.science/r/LASiR-B207>)
2. J. Zhang et al., "When Crypto Fails: Demystifying Cryptographic Defects in Ethereum Smart Contracts,"
   IEEE TSE 51(5), 2025. <https://doi.org/10.1109/TSE.2025.3551776>
   (artifact: <https://github.com/Jiashuo-Zhang/CryptoScan>, commit `257913106fde`)
3. Z. Zheng et al., "DAppSCAN: Building Large-Scale Datasets for Smart Contract Weaknesses in DApp
   Projects," IEEE TSE 50(6), 2024. <https://doi.org/10.1109/TSE.2024.3383422>

Contract sources of [1] were taken from the smart-contract-sanctuary mirrors
(<https://github.com/tintinweb/smart-contract-sanctuary>) at the commits the artifact lists.
