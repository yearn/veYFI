// SPDX-License-Identifier: MIT

pragma solidity 0.8.13;
import "./interfaces/IVotingEscrow.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract VoteDelegation is Ownable {
    struct Delegation {
        address to;
        uint256 until;
    }

    mapping(address => Delegation) public delegation;
    mapping(address => address[]) public delegated;

    uint256 public constant MAX_DELAGATED = 1_000;

    address public veToken;

    event Delegate(
        address indexed sender,
        address indexed recipient,
        uint256 until
    );
    event DelegationRemoved(address indexed from, address indexed to);
    event DelegationDurationIncreased(
        address indexed from,
        address indexed to,
        uint256 until
    );

    constructor(address _ve) {
        require(_ve != address(0x0), "_ve 0x0 address");
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
    @param _until delegate until, if under block.timestamp delegation can change immediately
     */
    function delegate(address _to, uint256 _until) external {
        _delegate(_to, _until);
    }

    /**
    @notice Delegate voting power to an address.
    @param _to the address that can use the voting power
     */
    function delegate(address _to) external {
        _delegate(_to, 0);
    }

    function _delegate(address _to, uint256 _until) internal {
        Delegation memory existingDelegation = delegation[msg.sender];

        require(
            existingDelegation.until < block.timestamp,
            "can't change delegation"
        );

        if (existingDelegation.to != address(0x0)) {
            _removeOldDelegation(msg.sender, existingDelegation.to);
        }

        delegation[msg.sender] = Delegation(_to, _until);
        if (_to != address(0x0)) {
            require(
                IVotingEscrow(veToken).balanceOf(msg.sender) != 0,
                "no power"
            );
            delegated[_to].push(msg.sender);
            require(delegated[_to].length <= MAX_DELAGATED, "max delegated");
        }
        emit Delegate(msg.sender, _to, _until);
    }

    function removeDelegation() external {
        Delegation memory existingDelegation = delegation[msg.sender];

        require(
            existingDelegation.until < block.timestamp,
            "can't change delegation"
        );
        address to = existingDelegation.to;
        if (to != address(0x0)) {
            _removeOldDelegation(msg.sender, to);
        }
        delete delegation[msg.sender];
        emit DelegationRemoved(msg.sender, to);
    }

    function increaseDelegationDuration(uint256 _until) external {
        Delegation storage existingDelegation = delegation[msg.sender];

        require(existingDelegation.until < _until, "must increase");
        existingDelegation.until = _until;
        emit DelegationDurationIncreased(
            msg.sender,
            existingDelegation.to,
            _until
        );
    }

    function _removeOldDelegation(address from, address to) internal {
        address[] storage delegatedList = delegated[to];
        uint256 length = delegatedList.length;
        for (uint256 i = 0; i < length; i++) {
            if (delegatedList[i] == from) {
                delegatedList[i] = delegated[to][length - 1];
                delegated[to].pop();
                break;
            }
        }
    }
}
