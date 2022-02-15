// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;

import "./interfaces/IGauge.sol";
import "./interfaces/IExtraReward.sol";
import "./interfaces/IGaugeFactory.sol";

contract GaugeFactory is IGaugeFactory {
    address public immutable deployedGauge;
    address public immutable deployedExtra;

    event GaugeCreated(address gauge);
    event ExtraRewardCreated(address extraReward);

    constructor(address _deployedGauge, address _deployedExtra) {
        deployedGauge = _deployedGauge;
        deployedExtra = _deployedExtra;
    }

    function createGauge(
        address _vault,
        address yfi,
        address gov,
        address manager,
        address ve,
        address veYfiRewardPool
    ) external override returns (address) {
        address newGauge = _clone(deployedGauge);
        IGauge(newGauge).initialize(
            _vault,
            yfi,
            gov,
            manager,
            ve,
            veYfiRewardPool
        );
        emit GaugeCreated(newGauge);

        return newGauge;
    }

    function createExtraReward(address gauge, address reward)
        external
        returns (address result)
    {
        address newExtraReward = _clone(deployedExtra);
        IExtraReward(newExtraReward).initialize(gauge, reward);
        emit ExtraRewardCreated(newExtraReward);

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
