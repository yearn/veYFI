# @version 0.3.10
"""
@title Vote weight measure
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Measures account current voting weight.
    Equal to veYFI balance at vote open.
"""

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view
implements: Measure

interface VotingEscrow:
    def totalSupply(_time: uint256) -> uint256: view
    def balanceOf(_account: address, _time: uint256) -> uint256: view

genesis: public(immutable(uint256))
voting_escrow: public(immutable(VotingEscrow))

WEEK_LENGTH: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 2 * WEEK_LENGTH

@external
def __init__(_genesis: uint256, _voting_escrow: address):
    """
    @notice Constructor
    @param _genesis Genesis timestamp
    @param _voting_escrow Voting escrow
    """
    genesis = _genesis
    voting_escrow = VotingEscrow(_voting_escrow)

@internal
@view
def _vote_open_time() -> uint256:
    return genesis + (block.timestamp - genesis) / EPOCH_LENGTH * EPOCH_LENGTH + WEEK_LENGTH

@external
@view
def total_vote_weight() -> uint256:
    """
    @notice Get total vote weight
    @return Total vote weight
    """
    return voting_escrow.totalSupply(self._vote_open_time())

@external
@view
def vote_weight(_account: address) -> uint256:
    """
    @notice Get account vote weight
    @param _account Account to get vote weight for
    @return Account vote weight
    """
    return voting_escrow.balanceOf(_account, self._vote_open_time())
