# @version 0.3.10

from vyper.interfaces import ERC20
implements: ERC20

interface ERC20Burnable:
    def transfer(_to: address, _amount: uint256) -> bool: nonpayable
    def burn(_amount: uint256): nonpayable
implements: ERC20Burnable

totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])

name: public(constant(String[9])) = "MockToken"
symbol: public(constant(String[4])) = "MOCK"
decimals: public(constant(uint8)) = 18

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

@external
def __init__():
    log Transfer(empty(address), msg.sender, 0)

@external
def transfer(_to: address, _value: uint256) -> bool:
    assert _to != empty(address)
    self.balanceOf[msg.sender] -= _value
    self.balanceOf[_to] += _value
    log Transfer(msg.sender, _to, _value)
    return True

@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    assert _to != empty(address)
    self.allowance[_from][msg.sender] -= _value
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    log Transfer(_from, _to, _value)
    return True

@external
def approve(_spender: address, _value: uint256) -> bool:
    self.allowance[msg.sender][_spender] = _value
    log Approval(msg.sender, _spender, _value)
    return True

@external
def mint(_account: address, _value: uint256):
    self.totalSupply += _value
    self.balanceOf[_account] += _value
    log Transfer(empty(address), _account, _value)

@external
def burn(_value: uint256):
    self.totalSupply -= _value
    self.balanceOf[msg.sender] -= _value
    log Transfer(msg.sender, empty(address), _value)

@external
def burn_from(_account: address, _value: uint256):
    self.totalSupply -= _value
    self.balanceOf[_account] -= _value
    log Transfer(_account, empty(address), _value)
