// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract MalleableWithdraw {
  address public immutable signer;
  mapping(bytes32 => bool) public usedSig;

  constructor(address signer_) { signer = signer_; }

  function withdrawBySig(
    address payable to, uint256 amount, uint8 v, bytes32 r, bytes32 s
  ) external {
    bytes32 sigId = keccak256(abi.encodePacked(r, s, v));
    require(!usedSig[sigId], "used");
    bytes32 digest = keccak256(abi.encode(to, amount, address(this), block.chainid));
    require(ecrecover(digest, v, r, s) == signer, "bad signature");
    usedSig[sigId] = true;
    to.transfer(amount);
  }
}

