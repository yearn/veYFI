// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

import "./interfaces/IGauge.sol";
import "./interfaces/IExtraReward.sol";
import "./interfaces/IGaugeFactory.sol";

/** @title  GaugeFactory
    @notice Creates Gauge and ExtraReward
    @dev Uses clone to create new contracts
 */
contract GaugeFactory is IGaugeFactory {
    address public immutable deployedGauge;
    address public immutable deployedExtra;

    event GaugeCreated(address indexed gauge);
    event ExtraRewardCreated(address indexed extraReward);

    constructor(address _deployedGauge, address _deployedExtra) {
        deployedGauge = _deployedGauge;
        deployedExtra = _deployedExtra;
    }

    /** @notice Create a new reward Gauge clone
        @param _vault the vault address.
        @param yfi the YFI token address.
        @param owner owner
        @param manager manager
        @param ve veYFI
        @param veYfiRewardPool veYfi RewardPool
        @return gauge address
    */
    function createGauge(
        address _vault,
        address yfi,
        address owner,
        address manager,
        address ve,
        address veYfiRewardPool
    ) external override returns (address) {
        address newGauge = _clone(deployedGauge);
        emit GaugeCreated(newGauge);
        IGauge(newGauge).initialize(
            _vault,
            yfi,
            owner,
            manager,
            ve,
            veYfiRewardPool
        );

        return newGauge;
    }

    /** @notice Create ExtraReward clone
        @param gauge the gauge associated with.
        @param reward The token to distribute as a rewards
        @param owner owner 
        @return ExtraReward address
    */
    function createExtraReward(
        address gauge,
        address reward,
        address owner
    ) external returns (address) {
        address newExtraReward = _clone(deployedExtra);
        emit ExtraRewardCreated(newExtraReward);
        IExtraReward(newExtraReward).initialize(gauge, reward, owner);

        return newExtraReward;
    }

    function _clone(address c) internal returns (address result) {
        bytes20 targetBytes = bytes20(c);
        assembly {
            let clone := mload(0x40)
            mstore(
                clone,
                0x3d602d80600a3d3981f3363d3d373d3d3d363d73000000000000000000000000
            )
            mstore(add(clone, 0x14), targetBytes)
            mstore(
                add(clone, 0x28),
                0x5af43d82803e903d91602b57fd5bf30000000000000000000000000000000000
            )
            result := create(0, clone, 0x37)
        }
    }
}
