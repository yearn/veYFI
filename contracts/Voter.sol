// SPDX-License-Identifier: MIT
pragma solidity 0.8.11;
import "./interfaces/IVotingEscrow.sol";

import "./interfaces/IGaugeFactory.sol";

contract Voter {
    address public ve; // immutable // the ve token that governs these contracts
    address public yfi; // immutable // reward token
    address public veYfiRewardPool; // immutable
    address public gaugefactory; // immutable
    uint256 public totalWeight; // total voting weight

    address[] public vaults; // all vaults viable for incentives
    mapping(address => address) public gauges; // vault => gauge
    mapping(address => address) public vaultForGauge; // gauge => vault
    mapping(address => uint256) public weights; // vault => weight
    mapping(address => mapping(address => uint256)) public votes; // address => vault => votes
    mapping(address => address[]) public vaultVote; // address => vault
    mapping(address => uint256) public usedWeights; // address => total voting weight of user
    mapping(address => bool) public isGauge;
    address public gov;

    event UpdatedGov(address gov);

    constructor(
        address _ve,
        address _yfi,
        address _gaugefactory,
        address _veYfiRewardPool
    ) {
        ve = _ve;
        yfi = _yfi;
        gaugefactory = _gaugefactory;
        veYfiRewardPool = _veYfiRewardPool;
        gov = msg.sender;
    }

    function reset() external {
        _reset(msg.sender);
    }

    function _reset(address _account) internal {
        address[] storage _vaultVote = vaultVote[_account];
        uint256 _vaultVoteCnt = _vaultVote.length;
        uint256 _totalWeight = 0;

        for (uint256 i = 0; i < _vaultVoteCnt; i++) {
            address _vault = _vaultVote[i];
            uint256 _votes = votes[_account][_vault];

            if (_votes > 0) {
                _totalWeight += _votes;
                weights[_vault] -= _votes;
                votes[_account][_vault] -= _votes;
            }
        }
        totalWeight -= _totalWeight;
        usedWeights[_account] = 0;
        delete vaultVote[_account];
    }

    function poke(address _account) external {
        address[] memory _vaultVote = vaultVote[_account];
        uint256 _vaultCnt = _vaultVote.length;
        uint256[] memory _weights = new uint256[](_vaultCnt);

        for (uint256 i = 0; i < _vaultCnt; i++) {
            _weights[i] = votes[_account][_vaultVote[i]];
        }

        _vote(_account, _vaultVote, _weights);
    }

    function _vote(
        address _account,
        address[] memory _vaultVote,
        uint256[] memory _weights
    ) internal {
        _reset(_account);
        uint256 _weight = IVotingEscrow(ve).balanceOf(_account);
        if (_weight == 0) return;

        uint256 _vaultCnt = _vaultVote.length;
        uint256 _totalVoteWeight = 0;
        uint256 _totalWeight = 0;
        uint256 _usedWeight = 0;

        for (uint256 i = 0; i < _vaultCnt; i++) {
            _totalVoteWeight += _weights[i];
        }

        for (uint256 i = 0; i < _vaultCnt; i++) {
            address _vault = _vaultVote[i];
            address _gauge = gauges[_vault];
            uint256 _vaultWeight = (_weights[i] * _weight) / _totalVoteWeight;

            if (isGauge[_gauge]) {
                _usedWeight += _vaultWeight;
                _totalWeight += _vaultWeight;
                weights[_vault] += _vaultWeight;
                vaultVote[_account].push(_vault);
                votes[_account][_vault] += _vaultWeight;
            }
        }
        totalWeight += _totalWeight;
        usedWeights[_account] = _usedWeight;
    }

    function vote(
        address _account,
        address[] calldata _vaultVote,
        uint256[] calldata _weights
    ) external {
        require(
            IVotingEscrow(ve).delegation(_account) == msg.sender ||
                _account == msg.sender
        );
        require(_vaultVote.length == _weights.length);
        _vote(_account, _vaultVote, _weights);
    }

    function vote(address[] calldata _vaultVote, uint256[] calldata _weights)
        external
    {
        require(_vaultVote.length == _weights.length);
        _vote(msg.sender, _vaultVote, _weights);
    }

    function setGov(address _gov) external {
        require(msg.sender == gov, "!authorized");

        require(_gov != address(0));
        gov = _gov;
        emit UpdatedGov(_gov);
    }

    function addVaultToRewards(
        address _vault,
        address gov,
        address rewardManager
    ) external returns (address) {
        require(msg.sender == gov, "exists");
        address _gauge = IGaugeFactory(gaugefactory).createGauge(
            _vault,
            yfi,
            gov,
            rewardManager,
            ve,
            veYfiRewardPool
        );
        gauges[_vault] = _gauge;
        vaultForGauge[_gauge] = _vault;
        isGauge[_gauge] = true;
        vaults.push(_vault);
        return _gauge;
    }
}
