# @version 0.3.10

interface Minter:
    def mint(_epoch: uint256) -> uint256: nonpayable

interface MockToken:
    def mint(_account: address, _amount: uint256): nonpayable

implements: Minter

token: immutable(MockToken)
controller: address
mintable: HashMap[uint256, uint256]

@external
def __init__(_token: address):
    token = MockToken(_token)

@external
def set_controller(_controller: address):
    self.controller = _controller

@external
def set_mintable(_epoch: uint256, _amount: uint256):
    self.mintable[_epoch] = _amount

@external
def mint(_epoch: uint256) -> uint256:
    assert msg.sender == self.controller
    mintable: uint256 = self.mintable[_epoch]
    if mintable > 0:
        token.mint(msg.sender, mintable)
        self.mintable[_epoch] = 0
    return mintable
