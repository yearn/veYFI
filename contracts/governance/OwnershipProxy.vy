# @version 0.3.10
"""
@title Ownership proxy
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Intended owner of all management roles in the entire protocol, outside of its own.
    Management role is allowed to execute arbitrary calls and is intended to be filled
    by the executor. This allows for easy upgrading and swapping to a new executor
    without having to migrate all owned management roles.
"""

management: public(address)

event Execute:
    by: indexed(address)
    contract: indexed(address)
    data: Bytes[2048]

event SetManagement:
    management: indexed(address)

@external
def __init__():
    """
    @notice Constructor
    """
    self.management = msg.sender

@external
def execute(_to: address, _data: Bytes[2048]):
    """
    @notice Execute an arbitary function call
    @param _to Contract to call
    @param _data Calldata of the call
    """
    assert msg.sender == self.management
    log Execute(msg.sender, _to, _data)
    raw_call(_to, _data)

@external
def set_management(_management: address):
    """
    @notice Set the new management address
    @param _management New management address
    """
    assert msg.sender == self
    assert _management != empty(address)
    self.management = _management
    log SetManagement(_management)
