// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract OwnerWallet {
  address public immutable owner;
  bytes32 public immutable loginDigest;

  constructor(address owner_) {
    owner = owner_;
    loginDigest = keccak256(abi.encodePacked("OwnerWallet login", owner_));
  }

  function isValidSignature(bytes32 hash, bytes calldata signature)
    external view returns (bytes4)
  {
    return _isOwnerSignature(hash, signature) ? bytes4(0x1626ba7e) : bytes4(0xffffffff);
  }

  function _isOwnerSignature(bytes32 hash, bytes calldata signature)
    internal view returns (bool)
  {
    return ECDSA.recover(loginDigest, signature) == owner;
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
