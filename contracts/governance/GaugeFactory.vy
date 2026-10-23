# @version 0.3.10
"""
@title Gauge factory
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Permissionless deployment of gauges.
    Gauges are minimal proxies to a gauge implementation contract
"""

interface Gauge:
    def initialize(_asset: address, _owner: address, _controller: address, _data: Bytes[1024]): nonpayable

management: public(address)
pending_management: public(address)
version: public(uint256)
implementation: public(address)
gauge_owner: public(address)
controller: public(address)
gauge_versions: public(HashMap[address, uint256])

event GaugeDeployed:
    asset: indexed(address)
    gauge: address

event SetImplementation:
    version: uint256
    implementation: address

event SetGaugeOwner:
    owner: address

event SetController:
    controller: address

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

event SetLegacyGauge:
    gauge: address

@external
def __init__(_controller: address):
    """
    @notice Constructor
    @param _controller Gauge controller
    """
    self.management = msg.sender
    self.gauge_owner = msg.sender
    self.version = 1
    self.controller = _controller

@external
def deploy_gauge(_asset: address, _data: Bytes[1024] = b"") -> address:
    """
    @notice Deploy a new gauge
    @param _asset The underlying asset for the gauge
    @param _data Additional data to pass on to the gauge during initialization (unused)
    """
    assert _asset != empty(address)
    version: uint256 = self.version
    assert version > 1

    gauge: address = create_minimal_proxy_to(self.implementation)
    Gauge(gauge).initialize(_asset, self.gauge_owner, self.controller, _data)
    self.gauge_versions[gauge] = version
    log GaugeDeployed(_asset, gauge)
    return gauge

@external
def set_implementation(_implementation: address) -> uint256:
    """
    @notice Set a new gauge implementation contract
    @param _implementation Implementation contract address
    @return New gauge version number
    @dev Only callable by management
    """
    
    assert msg.sender == self.management
    assert _implementation != empty(address)
    version: uint256 = self.version + 1
    self.version = version
    self.implementation = _implementation
    log SetImplementation(version, _implementation)
    return version

@external
def set_gauge_owner(_gauge_owner: address):
    """
    @notice Set a new owner for future gauges
    @param _gauge_owner New gauge owner
    @dev Only callable by management
    """
    assert msg.sender == self.management
    self.gauge_owner = _gauge_owner
    log SetGaugeOwner(_gauge_owner)

@external
def set_controller(_controller: address):
    """
    @notice Set a new gauge controller
    @param _controller New gauge controller
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _controller != empty(address)
    self.controller = _controller
    log SetController(_controller)

@external
def set_legacy_gauges(_gauges: DynArray[address, 8]):
    """
    @notice Mark gauges as legacy
    @param _gauges Gauges to be marked
    @dev Only callable by management
    """
    assert msg.sender == self.management
    for gauge in _gauges:
        assert self.gauge_versions[gauge] == 0
        self.gauge_versions[gauge] = 1
        log SetLegacyGauge(gauge)

@external
def set_management(_management: address):
    """
    @notice 
        Set the pending management address.
        Needs to be accepted by that account separately to transfer management over
    @param _management New pending management address
    """
    assert msg.sender == self.management
    self.pending_management = _management
    log PendingManagement(_management)

@external
def accept_management():
    """
    @notice 
        Accept management role.
        Can only be called by account previously marked as pending management by current management
    """
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender
    log SetManagement(msg.sender)
