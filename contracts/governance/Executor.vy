# @version 0.3.10
"""
@title Executor
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Responsible for executing governance decisions through a proxy.
    Only appointed governors are allowed to execute calls, subject to access control based on 
    the governor, the calling contract and the selector.
    Management has the power to enable and set/unset whitelists and blacklists.
    The management role is intended to be transferred to the proxy, making the system self-governing.
"""

interface Proxy:
    def execute(_to: address, _data: Bytes[2048]): nonpayable

enum Access:
    WHITELIST
    BLACKLIST

proxy: public(immutable(Proxy))
management: public(address)
pending_management: public(address)
governors: public(HashMap[address, bool])
access: public(HashMap[uint256, Access]) # target => access control setting
whitelisted: HashMap[uint256, HashMap[address, bool]] # target => governor => whitelisted
blacklisted: HashMap[uint256, HashMap[address, bool]] # target => governor => blacklisted

event Execute:
    by: indexed(address)
    contract: indexed(address)
    data: Bytes[2048]

event SetGovernor:
    by: indexed(address)
    governor: indexed(address)
    flag: bool

event SetAccess:
    by: indexed(address)
    contract: indexed(address)
    identifier: indexed(bytes4)
    access: Access

event Whitelist:
    contract: indexed(address)
    identifier: indexed(bytes4)
    by: indexed(address)
    whitelisted: bool

event Blacklist:
    contract: indexed(address)
    identifier: indexed(bytes4)
    by: indexed(address)
    blacklisted: bool

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

TARGET_MASK: public(constant(uint256)) = shift(1, 192) - 1
IDENTIFIER_MASK: constant(uint256) = shift(1, 32) - 1

@external
def __init__(_proxy: address):
    """
    @notice Constructor
    @param _proxy The ownership proxy
    """
    proxy = Proxy(_proxy)
    self.management = msg.sender
    self.governors[msg.sender] = True

@external
def execute_single(_to: address, _data: Bytes[2048]):
    """
    @notice Execute a single call
    @param _to The contract to call
    @param _data Calldata
    """
    assert self.governors[msg.sender]
    assert len(_data) >= 4
    identifier: bytes4 = convert(slice(_data, 0, 4), bytes4)
    target: uint256 = self._pack_target(_to, identifier)

    # check access control
    access: Access = self.access[target]
    if access == Access.BLACKLIST:
        assert not self.blacklisted[target][msg.sender]
    elif access == Access.WHITELIST:
        assert self.whitelisted[target][msg.sender]

    proxy.execute(_to, _data)
    log Execute(msg.sender, _to, _data)

@external
def execute(_script: Bytes[2048]):
    """
    @notice Execute a single script consisting of one or more calls
    @param _script Script to execute
    """
    assert self.governors[msg.sender]

    i: uint256 = 0
    for x in range(32):
        if i == len(_script):
            break
        assert i + 32 <= len(_script)
    
        # extract target and calldata size
        target: uint256 = extract32(_script, i, output_type=uint256) # calldata size (64) | address (160) | identifier (32)
        size: uint256 = shift(target, -192)
        target &= TARGET_MASK
        i += 28 # calldata size (8 bytes) + address (20 bytes)
        assert i + size <= len(_script)
        assert size >= 4 and size <= 2048

        # check access control
        access: Access = self.access[target]
        if access == Access.BLACKLIST:
            assert not self.blacklisted[target][msg.sender]
        elif access == Access.WHITELIST:
            assert self.whitelisted[target][msg.sender]

        contract: address = empty(address)
        identifier: bytes4 = empty(bytes4)
        contract, identifier = self._unpack_target(target)
        calldata: Bytes[2048] = slice(_script, i, size)

        i += size
        assert i <= len(_script)

        proxy.execute(contract, calldata)
        log Execute(msg.sender, contract, calldata)

    assert i == len(_script)

@external
@pure
def script(_to: address, _data: Bytes[2048]) -> Bytes[2080]:
    """
    @notice
        Generate script for a single call.
        Calls can be chained by concatenating their scripts
    @param _to The contract to call
    @param _data Calldata
    """
    assert len(_data) >= 4
    prefix: uint256 = shift(len(_data), 160) | convert(_to, uint256)
    return concat(convert(convert(prefix, uint224), bytes28), _data)

@external
def set_governor(_governor: address, _flag: bool):
    """
    @notice Set the governor role
    @param _governor The account to set the role for
    @param _flag True: set governor, False: unset governor
    """
    assert msg.sender == self.management
    assert _governor != empty(address)
    self.governors[_governor] = _flag
    log SetGovernor(msg.sender, _governor, _flag)

@external
def set_access(_contract: address, _identifier: bytes4, _access: Access):
    """
    @notice Set access control for a contract+identifier combination
    @param _contract Contract address
    @param _identifier Function identifier
    @param _access Whether to enable whitelist or blacklist. Zero to disable access control
    """
    assert msg.sender == self.management
    assert _contract != empty(address)
    assert convert(_access, uint256) < 3
    target: uint256 = self._pack_target(_contract, _identifier)
    self.access[target] = _access
    log SetAccess(msg.sender, _contract, _identifier, _access)

@external
def whitelist(_contract: address, _identifier: bytes4, _caller: address, _whitelisted: bool):
    """
    @notice Whitelist a governor for a contract+identifier combination
    @param _contract Contract address
    @param _identifier Function identifier
    @param _caller Governor to apply the whitelist to
    @param _whitelisted True: add to whitelist, False: remove from whitelist
    """
    assert msg.sender == self.management
    assert _contract != empty(address)
    target: uint256 = self._pack_target(_contract, _identifier)
    self.whitelisted[target][_caller] = _whitelisted
    log Whitelist(_contract, _identifier, _caller, _whitelisted)

@external
@view
def is_whitelisted(_contract: address, _identifier: bytes4, _caller: address) -> bool:
    """
    @notice Query if a governor is whitelisted to call a contract+identifier combination
    @param _contract Contract address
    @param _identifier Function identifier
    @param _caller Governor
    @return True: on whitelist, False: not on whitelist
    """
    target: uint256 = self._pack_target(_contract, _identifier)
    return self.whitelisted[target][_caller]

@external
@view
def has_whitelist(_contract: address, _identifier: bytes4) -> bool:
    """
    @notice Query if a contract+identifier combination has whitelist enabled
    @param _contract Contract address
    @param _identifier Function identifier
    @return True: whitelist enabled, False: whitelist disabled
    """
    target: uint256 = self._pack_target(_contract, _identifier)
    return self.access[target] == Access.WHITELIST

@external
def blacklist(_contract: address, _identifier: bytes4, _caller: address, _blacklisted: bool):
    """
    @notice Blacklist a governor for a contract+identifier combination
    @param _contract Contract address
    @param _identifier Function identifier
    @param _caller Governor to apply the blacklist to
    @param _blacklisted True: add to blacklist, False: remove from blacklist
    """
    assert msg.sender == self.management
    assert _contract != empty(address)
    target: uint256 = self._pack_target(_contract, _identifier)
    self.blacklisted[target][_caller] = _blacklisted
    log Blacklist(_contract, _identifier, _caller, _blacklisted)

@external
@view
def is_blacklisted(_contract: address, _identifier: bytes4, _caller: address) -> bool:
    """
    @notice Query if a governor is blacklisted to call a contract+identifier combination
    @param _contract Contract address
    @param _identifier Function identifier
    @param _caller Governor
    @return True: on blacklist, False: not on blacklist
    """
    target: uint256 = self._pack_target(_contract, _identifier)
    return self.blacklisted[target][_caller]

@external
@view
def has_blacklist(_contract: address, _identifier: bytes4) -> bool:
    """
    @notice Query if a contract+identifier combination has blacklist enabled
    @param _contract Contract address
    @param _identifier Function identifier
    @return True: blacklist enabled, False: blacklist disabled
    """
    target: uint256 = self._pack_target(_contract, _identifier)
    return self.access[target] == Access.BLACKLIST

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

@internal
@pure
def _pack_target(_contract: address, _identifier: bytes4) -> uint256:
    """
    @notice Pack a contract+identifier into a single word
    """
    return shift(convert(_contract, uint256), 32) | convert(_identifier, uint256)

@internal
@pure
def _unpack_target(_target: uint256) -> (address, bytes4):
    """
    @notice Unpack a contract+identifier from a single word
    """
    return convert(shift(_target, -32), address), convert(convert(_target & IDENTIFIER_MASK, uint32), bytes4)
