# @version 0.3.10

from vyper.interfaces import ERC20

interface Taker:
    def auctionTakeCallback(_id: bytes32, _sender: address, _taken: uint256, _needed: uint256, _data: Bytes[1024]): nonpayable

implements: Taker

want: immutable(ERC20)
id: bytes32
sender: address
taken: uint256
data: Bytes[1024]

@external
def __init__(_want: address):
    want = ERC20(_want)

@external
def auctionTakeCallback(_id: bytes32, _sender: address, _taken: uint256, _needed: uint256, _data: Bytes[1024]):
    assert _id == self.id
    assert _sender == self.sender
    assert _taken == self.taken
    assert _data == self.data
    assert want.approve(msg.sender, _needed, default_return_value=True)

@external
def set_id(_id: bytes32):
    self.id = _id

@external
def set_sender(_sender: address):
    self.sender = _sender

@external
def set_taken(_taken: uint256):
    self.taken = _taken

@external
def set_data(_data: Bytes[1024]):
    self.data = _data
