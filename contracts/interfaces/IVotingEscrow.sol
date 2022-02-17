// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IVotingEscrow is IERC20 {
    struct LockedBalance {
        int128 amount;
        uint256 end;
    }

    function balanceOf(address) external view returns (uint256);

    function totalSupply() external view returns (uint256);
    
    function locked__end(address) external returns(uint256);

    function locked(address) external view returns (LockedBalance memory);

    function deposit_for(address, uint256) external;
}
