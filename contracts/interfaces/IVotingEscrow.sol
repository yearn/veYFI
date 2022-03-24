// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IVotingEscrow is IERC20 {
    struct LockedBalance {
        int128 amount;
        uint256 end;
    }

    function totalSupply() external view returns (uint256);

    function locked__end(address) external view returns (uint256);

    function locked(address) external view returns (LockedBalance memory);

    function deposit_for(address, uint256) external;

    function migration() external view returns (bool);
}
