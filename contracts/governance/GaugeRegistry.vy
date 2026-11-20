# @version 0.3.10
"""
@title Gauge registry
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Registry for approved gauges.
    Gauges can be added by governance, which makes them eligible
    to be voted on in the gauge controller.
    Each registered gauge corresponds to a unique underlying vault.
"""

interface Controller:
    def whitelist(_gauge: address, _whitelisted: bool): nonpayable

interface Factory:
    def gauge_versions(_gauge: address) -> uint256: view

interface Gauge:
    def asset() -> address: view

management: public(address)
pending_management: public(address)
controller: public(Controller)
factory: public(Factory)

vault_count: public(uint256)
vaults: public(address[99999])
vault_gauge_map: public(HashMap[address, address]) # vault => gauge

event Register:
    gauge: indexed(address)
    idx: uint256

event Deregister:
    gauge: indexed(address)
    idx: uint256

event UpdateIndex:
    old_idx: indexed(uint256)
    idx: uint256

event SetController:
    controller: address

event SetFactory:
    factory: address

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

@external
def __init__(_controller: address, _factory: address):
    """
    @notice Constructor
    @param _controller Gauge controller
    @param _factory Gauge factory
    """
    self.management = msg.sender
    self.controller = Controller(_controller)
    self.factory = Factory(_factory)

@external
@view
def gauges(_idx: uint256) -> address:
    """
    @notice Get a gauge at a certain index in the list
    @param _idx Index of the gauge
    @return Gauge at the specified index
    """
    vault: address = self.vaults[_idx]
    assert vault != empty(address)
    return self.vault_gauge_map[vault]

@external
def register(_gauge: address) -> uint256:
    """
    @notice Add a gauge to the registry
    @param _gauge Gauge address
    @return Index of the vault
    @dev Gauge has to originate from the factory
    @dev Underlying vault cannot already have a registered gauge
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert self.factory.gauge_versions(_gauge) > 0
    vault: address = Gauge(_gauge).asset()
    assert self.vault_gauge_map[vault] == empty(address)

    idx: uint256 = self.vault_count
    self.vault_count = idx + 1
    self.vaults[idx] = vault
    self.vault_gauge_map[vault] = _gauge
    self.controller.whitelist(_gauge, True)
    log Register(_gauge, idx)
    return idx

@external
def deregister(_gauge: address, _idx: uint256):
    """
    @notice Remove a gauge from the registry
    @param _gauge Gauge address
    @param _idx Vault index
    @dev Only callable by management
    """
    assert msg.sender == self.management
    vault: address = Gauge(_gauge).asset()
    assert self.vault_gauge_map[vault] == _gauge
    assert self.vaults[_idx] == vault

    # swap last entry in array with the one being deleted
    # and shorten array by one
    max_idx: uint256 = self.vault_count - 1
    self.vault_count = max_idx
    log Deregister(_gauge, _idx)
    if _idx != max_idx:
        self.vaults[_idx] = self.vaults[max_idx]
        log UpdateIndex(max_idx, _idx)
    self.vaults[max_idx] = empty(address)
    self.vault_gauge_map[vault] = empty(address)
    self.controller.whitelist(_gauge, False)

@external
@view
def registered(_gauge: address) -> bool:
    """
    @notice Check whether a gauge is registered
    @param _gauge Gauge address
    @return Registration status
    """
    vault: address = Gauge(_gauge).asset()
    return self.vault_gauge_map[vault] == _gauge

@external
def set_controller(_controller: address):
    """
    @notice Set a new gauge controller
    @param _controller New gauge controller
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _controller != empty(address)
    self.controller = Controller(_controller)
    log SetController(_controller)

@external
def set_factory(_factory: address):
    """
    @notice Set a new factory
    @param _factory New factory
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _factory != empty(address)
    self.factory = Factory(_factory)
    log SetFactory(_factory)

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
