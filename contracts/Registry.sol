// SPDX-License-Identifier: MIT

pragma solidity 0.8.13;
import "./interfaces/IVotingEscrow.sol";
import "./interfaces/IGaugeFactory.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";

/** @title Voter
    @notice veYFI holders will vote for gauge allocation to vault tokens.
 */

contract Registry is Ownable {
    using EnumerableSet for EnumerableSet.AddressSet;
    address public veToken; // the ve token that governs these contracts
    address public yfi; // immutable // reward token
    address public veYfiRewardPool; // immutable
    address public gaugefactory; // immutable

    EnumerableSet.AddressSet private _vaults;
    mapping(address => address) public gauges; // vault => gauge
    mapping(address => address) public vaultForGauge; // gauge => vault
    mapping(address => bool) public isGauge;

    event VaultAdded(address indexed vault);
    event VaultRemoved(address indexed vault);
    event UpdatedVeToken(address indexed ve);

    constructor(
        address _ve,
        address _yfi,
        address _gaugefactory,
        address _veYfiRewardPool
    ) {
        require(_ve != address(0x0), "_ve 0x0 address");
        require(_yfi != address(0x0), "_yfi 0x0 address");
        require(_gaugefactory != address(0x0), "_gaugefactory 0x0 address");
        require(
            _veYfiRewardPool != address(0x0),
            "_veYfiRewardPool 0x0 address"
        );

        veToken = _ve;
        yfi = _yfi;
        gaugefactory = _gaugefactory;
        veYfiRewardPool = _veYfiRewardPool;
    }

    function setVe(address _ve) external onlyOwner {
        veToken = _ve;
        emit UpdatedVeToken(_ve);
    }

    /** 
    @return The list of vaults with gauge that are possible to vote for.
    */
    function getVaults() external view returns (address[] memory) {
        return _vaults.values();
    }

    /** 
    @notice Add a vault to the list of vaults that recieves rewards.
    @param _vault vault address
    @param _owner owner.
    @param _rewardManager address in charge of managing additional rewards
    */
    function addVaultToRewards(
        address _vault,
        address _owner,
        address _rewardManager
    ) external onlyOwner returns (address) {
        require(gauges[_vault] == address(0x0), "exist");

        address _gauge = IGaugeFactory(gaugefactory).createGauge(
            _vault,
            yfi,
            _owner,
            _rewardManager,
            veToken,
            veYfiRewardPool
        );
        gauges[_vault] = _gauge;
        vaultForGauge[_gauge] = _vault;
        isGauge[_gauge] = true;
        _vaults.add(_vault);
        emit VaultAdded(_vault);
        return _gauge;
    }

    /** 
    @notice Remove a vault from the list of vaults recieving rewards.
    @param _vault vault address
    */
    function removeVaultFromRewards(address _vault) external onlyOwner {
        require(gauges[_vault] != address(0x0), "!exist");
        address gauge = gauges[_vault];

        _vaults.remove(_vault);

        gauges[_vault] = address(0x0);
        vaultForGauge[gauge] = address(0x0);
        isGauge[gauge] = false;
        emit VaultRemoved(_vault);
    }
}
