// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract ReplayBurn {
  address public immutable signer;
  mapping(address => uint256) public burned;
  mapping(bytes32 => bool) public used;

  constructor(address signer_) { signer = signer_; }

  function burnBySig(address holder, uint256 amount, bytes32 id, bytes calldata sig)
    external
  {
    require(!used[id], "used");
    bytes32 digest = keccak256(
      abi.encode(holder, amount, id, address(this), block.chainid)
    );
    require(_verify(digest, sig), "bad signature");
    used[id] = true;
    burned[holder] += amount;
  }

  function _verify(bytes32 digest, bytes calldata sig) internal view returns (bool) {
    return ECDSA.recover(digest, sig) == signer;
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
