// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract TypedOrder {
  bytes32 private constant ORDER_TYPEHASH = keccak256(
    "Order(address maker,uint256 amount,address token,uint256 nonce,uint256 deadline)"
  );
  bytes32 private constant DOMAIN_TYPEHASH = keccak256(
    "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
  );
  mapping(address => uint256) public nonces;
  mapping(address => mapping(address => uint256)) public filled;

  function fill(
    address maker, address token, uint256 amount, uint256 nonce, uint256 deadline,
    bytes calldata sig
  ) external {
    require(block.timestamp <= deadline, "expired");
    require(nonce == nonces[maker], "wrong nonce");
    bytes32 structHash = keccak256(
      abi.encode(ORDER_TYPEHASH, maker, token, amount, nonce, deadline)
    );
    bytes32 digest = keccak256(
      abi.encodePacked("\x19\x01", _domainSeparator(), structHash)
    );
    require(ECDSA.recover(digest, sig) == maker, "bad signature");
    nonces[maker] = nonce + 1;
    filled[maker][token] += amount;
  }

  function _domainSeparator() internal view returns (bytes32) {
    return keccak256(abi.encode(
      DOMAIN_TYPEHASH, keccak256(bytes("TypedOrder")), keccak256(bytes("1")),
      block.chainid, address(this)
    ));
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
