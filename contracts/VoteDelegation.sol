// SPDX-License-Identifier: MIT

pragma solidity 0.8.12;
import "./interfaces/IVotingEscrow.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract VoteDelegation is Ownable {
    mapping(address => address) public delegation;
    mapping(address => address[]) public delegated;

    uint256 MAX_DELAGATED = 1_000;

    address public veToken;

    event Delegation(address sender, address recipient);

    constructor(address _ve) {
        veToken = _ve;
    }

    /** 
    @notice get the list of account that have delegated power to _account
    @param _account account to check
    @return The list of account addresses.
    */
    function getDelegated(address _account)
        external
        view
        returns (address[] memory)
    {
        return delegated[_account];
    }

    /**
    @notice Delegate voting power to an address.
    @param _to the address that can use the voting power
     */
    function delegate(address _to) external {
        address oldTo = delegation[msg.sender];

        if (oldTo != address(0x0)) {
            address[] storage delgateList = delegated[oldTo];
            uint256 length = delgateList.length;
            for (uint256 i = 0; i < length; i++) {
                if (delgateList[i] == msg.sender) {
                    delgateList[i] = delegated[oldTo][length - 1];
                    delegated[oldTo].pop();
                    break;
                }
            }
        }

        delegation[msg.sender] = _to;
        if (_to != address(0x0)) {
            require(
                IVotingEscrow(veToken).balanceOf(msg.sender) != 0,
                "no power"
            );
            require(delegated[_to].length < MAX_DELAGATED, "max delegated");
            delegated[_to].push(msg.sender);
        }
        emit Delegation(msg.sender, _to);
    }
}
