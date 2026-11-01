# Manual review of detector findings

Written on 2026-10-31, before any sample was drawn. Each sampled finding is classified by reading the
reported function, the helpers it calls and the state it uses.

- **weakness**: the reported function has the weakness that the detector's rule describes. Whether
  an attacker can profit from it is **not** considered: a signature problem without economic gain
  still counts.
- **false alarm**: the code handles the signature correctly for this rule and the report is wrong.
- **unclear**: the decision needs code that is not in the analysed file (an external library or
  contract). Unclear cases are reported separately and left out of the precision.

Each row of `<detector>.csv` gets a verdict and a one-line reason that names the line or construct.

## Per detector

- **signature-malleability**: a weakness if a path of the function reaches a recovery that accepts
  a high `s` (no `s <= n/2` check before `ecrecover`), normalises `v` permissively (`v += 27` for
  any value, `v % 2`, two recoveries), or accepts several encodings while the raw signature is the
  one-time key. A false alarm if `s` is bounded and `v` is checked strictly on every path, for example
  through OpenZeppelin `ECDSA.recover`.
- **nonce-management**: a weakness if the nonce is not part of the signed hash, the nonce check can
  be bypassed (an `||` branch) or is narrowing, the signer's own nonce is not advanced or marked used
  after a successful check, or another function can reset or decrease it. A false alarm if the
  signer's nonce is signed, checked and advanced, in any form (struct field, `add(1)`, helper,
  `_useNonce`).
- **eip712-implementation**: a weakness if the domain lacks or fixes the chain id or verifying
  contract, or takes them from caller input; the type string does not match the encoded fields
  (number, order, type); a dynamic field is not hashed; the final digest has a wrong prefix or
  encoding; or a parameter that decides the effect is not signed. A false alarm if the implementation
  follows EIP-712.
- **eip1271-verification**: a weakness if a wallet's `isValidSignature` ignores the hash or the
  signature, or returns the magic value for an invalid signature; or a caller accepts any non-zero
  or unchecked return, does not check the return length, uses a state-changing call, or lets the
  attacker choose the validator. A false alarm otherwise.
- **signature-freshness**: a weakness if a state-changing authorization has no signed time limit and
  no signed, revocable version or nonce; if a signed deadline is not enforced against
  `block.timestamp` or is enforced only as a lower bound; or if the deadline is not signed. A false
  alarm if a signed limit is enforced or the authorization is revocable.

## Clarification added during the review

Added while reviewing the nonce-management sample, after the samples were drawn. A one-time state that
plays the role of the nonce (a used-hash map, or a per-signer flag such as `receipt.hasVoted`) counts as
replay protection. A signature with no nonce and no one-time state is a weakness even when it is
reusable by design, such as an allow-list pass limited only by a per-wallet cap; such rows are tagged
`[reusable pass]` in the reason so that they can be counted separately.

Added while reviewing the eip712-implementation sample: a domain separator computed once (in the
constructor or an initializer) and never recomputed when `block.chainid` changes is read as "fixes the
chain id"; EIP-2612 names this replay risk after a chain split. Such rows are tagged `[cached domain]`.

Added while reviewing the samples of the final detector version (results/run8 and results/run9, drawn
with the same seed):
- signature-freshness: a signed one-time identifier that is consumed (a voucher counter, a transaction
  id, a mint key) counts as the nonce of the criterion.
- eip1271-verification: a wallet that verifies the supplied hash as it is, without binding it to its own
  address, is not counted as a weakness; the standard does not require re-hashing, and the detector only
  reports an explicit pass-through helper.
