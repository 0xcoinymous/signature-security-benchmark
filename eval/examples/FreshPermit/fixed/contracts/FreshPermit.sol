// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract FreshPermit {
  mapping(address => mapping(address => uint256)) public allowance;
  mapping(address => uint256) public nonces;

  function permit(
    address owner, address spender, uint256 value, uint256 nonce, uint256 deadline,
    bytes calldata sig
  ) external {
    require(block.timestamp <= deadline, "expired");
    require(nonce == nonces[owner], "wrong nonce");
    bytes32 digest = keccak256(
      abi.encode(owner, spender, value, nonce, deadline, address(this), block.chainid)
    );
    require(ECDSA.recover(digest, sig) == owner, "bad signature");
    nonces[owner] = nonce + 1;
    allowance[owner][spender] = value;
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
