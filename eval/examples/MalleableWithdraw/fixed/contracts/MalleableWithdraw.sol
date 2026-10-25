// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract MalleableWithdraw {
  uint256 private constant HALF_N =
    0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;
  address public immutable signer;
  mapping(bytes32 => bool) public used;

  constructor(address signer_) { signer = signer_; }

  function withdrawBySig(
    address payable to, uint256 amount, bytes32 id, uint8 v, bytes32 r, bytes32 s
  ) external {
    bytes32 digest = keccak256(
      abi.encode(to, amount, id, address(this), block.chainid)
    );
    require(!used[digest], "used");
    require(uint256(s) <= HALF_N, "high s");
    require(v == 27 || v == 28, "bad v");
    require(ecrecover(digest, v, r, s) == signer, "bad signature");
    used[digest] = true;
    to.transfer(amount);
  }
}

