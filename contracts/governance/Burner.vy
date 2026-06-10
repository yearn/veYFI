# @version 0.3.10
"""
@title Burner
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Burns reward tokens.
    Used by the gauge controller to burn rewards from blank votes.
"""

interface Token:
    def burn(_account: address, _amount: uint256): nonpayable

interface Burner:
    def burn(_epoch: uint256, _amount: uint256): nonpayable
    
implements: Burner

token: public(immutable(Token))
burned: public(HashMap[address, uint256])

event Burn:
    controller: indexed(address)
    epoch: indexed(uint256)
    amount: uint256

@external
def __init__(_token: address):
    """
    @notice Constructor
    @param _token Token address
    """
    token = Token(_token)

@external
def burn(_epoch: uint256, _amount: uint256):
    """
    @notice Burn tokens
    @param _epoch Epoch this burn belongs to
    @param _amount Amount of tokens to be burned from caller
    @dev Requires prior approval
    """
    self.burned[msg.sender] += _amount
    token.burn(msg.sender, _amount)
    log Burn(msg.sender, _epoch, _amount)
