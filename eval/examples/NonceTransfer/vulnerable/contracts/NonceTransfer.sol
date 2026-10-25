// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract NonceTransfer {
  mapping(address => uint256) public balances;
  mapping(address => uint256) public nonces;

  function transferBySig(
    address from, address to, uint256 amount, uint256 nonce, bytes calldata sig
  ) external {
    require(nonce == nonces[from], "wrong nonce");
    bytes32 digest = keccak256(
      abi.encode(from, to, amount, nonce, address(this), block.chainid)
    );
    require(ECDSA.recover(digest, sig) == from, "bad signature");
    nonces[msg.sender] = nonce + 1;
    balances[from] -= amount;
    balances[to] += amount;
  }
}

library ECDSA {
  function recover(bytes32 hash, bytes memory sig) internal pure returns (address) {
    (bytes32 r, bytes32 s, uint8 v) = abi.decode(sig, (bytes32, bytes32, uint8));
    require(
      uint256(s) <= 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0,
      "high s"
    );
    require(v == 27 || v == 28, "bad v");
    address a = ecrecover(hash, v, r, s);
    require(a != address(0), "zero");
    return a;
  }
}
