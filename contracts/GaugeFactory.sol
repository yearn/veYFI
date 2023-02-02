// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;

import "./interfaces/IGauge.sol";
import "./interfaces/IExtraReward.sol";
import "./interfaces/IGaugeFactory.sol";

/** @title  GaugeFactory
    @notice Creates Gauge and ExtraReward
    @dev Uses clone to create new contracts
 */
contract GaugeFactory is IGaugeFactory {
    address public immutable deployedGauge;

    event GaugeCreated(address indexed gauge);
    event ExtraRewardCreated(address indexed extraReward);

    constructor(address _deployedGauge) {
        deployedGauge = _deployedGauge;
    }

    /** @notice Create a new reward Gauge clone
        @param _vault the vault address.
        @param _owner owner
        @return gauge address
    */
    function createGauge(
        address _vault,
        address _owner
    ) external override returns (address) {
        address newGauge = _clone(deployedGauge);
        emit GaugeCreated(newGauge);
        IGauge(newGauge).initialize(_vault, _owner);

        return newGauge;
    }

    function _clone(address _source) internal returns (address result) {
        bytes20 targetBytes = bytes20(_source);
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
