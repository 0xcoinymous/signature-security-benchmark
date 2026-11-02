# Label review of reported pairs

Written on 2026-11-02, before any pair was judged.

The source studies label a (contract, type) pair vulnerable only when the weakness is exploitable in their
sense, for example replay that lets an attacker gain funds. This study counts every signature weakness,
whether or not money can be taken. Every scored pair labelled 0 by its source that any of the three tools
reports in the findings view (extended Aderyn with the detectors scored for the type, Slither with its
signature detectors; stock Aderyn reports nothing in this view) is re-examined by reading the contract.
`label` is the label used for scoring: 1 if the contract has the weakness of the type as defined below,
0 if it does not. The source label is kept in `source_label`.

- **replay** (signature replay, general): a function that verifies a signature and changes state accepts
  the same signature more than once in this contract (no nonce, used-flag or other one-time state that
  the signature binds), or the signed message is bound neither to this contract nor to the chain, so it
  is valid on another deployment or chain. A signature that is reusable by design (an allow-list pass
  limited only by a per-wallet cap) counts as reusable.
- **replay_single**: the first case only (reuse within the same contract).
- **replay_cross_contract**: the signed message does not bind the verifying contract (`address(this)` or
  an EIP-712 domain with `verifyingContract`), and the contract changes state on it.
- **replay_cross_chain**: the signed message does not bind the chain (`block.chainid`, a chain id in the
  EIP-712 domain, or an address that only exists on one chain is not enough), and the contract changes
  state on it.
- **malleability**: a recovery accepts a non-canonical signature (no `s <= n/2` bound, or a permissive
  `v` normalisation) on a state-changing path.

A pair whose reported code cannot be judged without code outside the file keeps label 0.
