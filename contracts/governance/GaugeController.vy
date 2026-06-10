# @version 0.3.10
"""
@title Gauge controller
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Controls gauge emissions as defined in YIP-73.
    - Gauges can be whitelisted, making them eligible for emissions in future epochs
    - Accounts with a vote weight can distribute their weight over whitelisted gauges every epoch
    - At the end of the epoch the tokens are minted and distributed according to their received vote weights
    - Governance can reserve a percentage of emissions to specific gauges, prior to any votes
    - These reserved emissions are taken out of the pool of votable emissions
    - Votes can be blank. Emissions due to blank votes are partially burned and partially
        reallocated to next epoch
"""

from vyper.interfaces import ERC20

interface Minter:
    def mint(_epoch: uint256) -> uint256: nonpayable

interface Burner:
    def burn(_epoch: uint256, _amount: uint256): nonpayable

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view

genesis: public(immutable(uint256))
token: public(immutable(ERC20))
management: public(address)
pending_management: public(address)
whitelister: public(address)
legacy_operator: public(address)
measure: public(Measure)
minter: public(Minter)
burner: public(Burner)

packed_emission: uint256 # (epoch, global cumulative emission, global current emission)
blank_emission: public(uint256)
packed_epoch_emission: HashMap[uint256, uint256] # epoch => (_, emission, reserved)
packed_gauge_emission: HashMap[address, uint256] # gauge => (epoch, cumulative emission, current emission)
gauge_claimed: public(HashMap[address, uint256]) # gauge => claimed

blank_burn_points: public(uint256)
reserved_points: public(uint256)
packed_gauge_reserved: HashMap[address, uint256] # gauge => (_, points, last global cumulative emission)
gauge_whitelisted: public(HashMap[address, bool]) # gauge => whitelisted?
legacy_gauge: public(HashMap[address, bool]) # gauge => legacy?

votes: public(HashMap[uint256, uint256]) # epoch => total votes
votes_user: public(HashMap[address, HashMap[uint256, uint256]]) # user => epoch => votes
gauge_votes: public(HashMap[uint256, HashMap[address, uint256]]) # epoch => gauge => votes
gauge_votes_user: public(HashMap[address, HashMap[uint256, HashMap[address, uint256]]]) # user => epoch => gauge => votes

event NewEpoch:
    epoch: uint256
    emission: uint256
    reserved: uint256
    burned: uint256
    blank: uint256

event Claim:
    gauge: indexed(address)
    amount: uint256

event Vote:
    epoch: uint256
    account: indexed(address)
    gauge: indexed(address)
    votes: uint256

event Whitelist:
    gauge: indexed(address)
    whitelisted: bool

event SetReservedPoints:
    gauge: indexed(address)
    points: uint256

event SetBlankBurnPoints:
    points: uint256

event SetLegacyGauge:
    gauge: indexed(address)
    legacy: bool

event SetWhitelister:
    whitelister: address

event SetLegacyOperator:
    operator: address

event SetMeasure:
    measure: address

event SetMinter:
    minter: address

event SetBurner:
    burner: address

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

WEEK_LENGTH: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 2 * WEEK_LENGTH
POINTS_SCALE: constant(uint256) = 10_000

MASK: constant(uint256) = 2**112 - 1
EPOCH_MASK: constant(uint256) = 2**32 - 1

@external
def __init__(_genesis: uint256, _token: address, _measure: address, _minter: address, _burner: address):
    """
    @notice Constructor
    @param _genesis Genesis timestamp
    @param _token Reward token address
    @param _measure Vote weight measure
    @param _minter Reward token minter
    @param _burner Reward token burner
    @dev Genesis should be picked at least one full epoch in the past
    """
    genesis = _genesis
    token = ERC20(_token)
    self.management = msg.sender
    self.whitelister = msg.sender
    self.legacy_operator = msg.sender
    self.measure = Measure(_measure)
    self.minter = Minter(_minter)
    self.burner = Burner(_burner)

    assert self._epoch() > 0

@external
@view
def epoch() -> uint256:
    """
    @notice Get the current epoch
    @return Current epoch
    """
    return self._epoch()

@internal
@view
def _epoch() -> uint256:
    return (block.timestamp - genesis) / EPOCH_LENGTH

@external
@view
def vote_open() -> bool:
    """
    @notice Check whether the vote is currently open
    @return True: vote is open, False: vote is closed
    """
    return self._vote_open()

@internal
@view
def _vote_open() -> bool:
    return (block.timestamp - genesis) % EPOCH_LENGTH >= WEEK_LENGTH

@external
@view
def votes_available(_account: address) -> uint256:
    """
    @notice Get amount of votes still available
    @param _account Account to check for
    @return Amount of votes still available
    """
    total: uint256 = self.measure.vote_weight(_account)
    epoch: uint256 = self._epoch()
    return total - self.votes_user[_account][epoch]

@external
@view
def emission() -> (uint256, uint256, uint256):
    """
    @notice Get overall emission information
    @return Tuple with:
        - Last finalized epoch. At most one behind the current epoch
        - Cumulative emission for all gauges until the last finalized epoch
        - Emission for all gauges in the last finalized epoch
    """
    return self._unpack(self.packed_emission)

@external
@view
def epoch_emission(_epoch: uint256) -> (uint256, uint256):
    """
    @notice Get emission information for a specific epoch
    @param _epoch Epoch
    @return Tuple with:
        - Emission for all gauges in the epoch
        - Reserved emission in the epoch
    @dev The total emission is inclusive of the reserved emission
    """
    return self._unpack_two(self.packed_epoch_emission[_epoch])

@external
@view
def gauge_emission(_gauge: address) -> (uint256, uint256, uint256):
    """
    @notice Get emission information for a specific gauge
    @param _gauge Gauge address
    @return Tuple with:
        - Last updated epoch. At most equal to the last finalized epoch
        - Cumulative emission for this gauge until the last updated epoch
        - Emission for this gauge in the last finalized epoch
    """
    return self._unpack(self.packed_gauge_emission[_gauge])

@external
@view
def gauge_reserved_points(_gauge: address) -> uint256:
    """
    @notice Get reserved points for a gauge
    @param _gauge Gauge address
    @return Reserved points (bps)
    @dev Gauges with reserved emissions receive a fixed percentage
        of all the emissions, which is subtracted from the available
        emissions for votes
    """
    return self._unpack_two(self.packed_gauge_reserved[_gauge])[0]

@external
@view
def gauge_reserved_last_cumulative(_gauge: address) -> uint256:
    """
    @notice Get gauge's last known overall cumulative emissions
    @param _gauge Gauge address
    @return Last known overall cumulative emission
    @dev Used to fast-forward gauge emissions without having to iterate
    """
    return self._unpack_two(self.packed_gauge_reserved[_gauge])[1]

@external
def vote(_gauges: DynArray[address, 32], _votes: DynArray[uint256, 32]):
    """
    @notice Vote for specific gauges
    @param _gauges Gauge addresses
    @param _votes Votes as a fraction of users total vote weight (bps)
    @dev Can be called multiple times
    @dev Votes are additive, they cant be undone
    @dev Votes can be blank by using the zero address
    """
    assert len(_gauges) == len(_votes)
    assert self._vote_open()

    assert self._update_emission()
    available: uint256 = self.measure.vote_weight(msg.sender)
    epoch: uint256 = self._epoch()

    used: uint256 = 0
    for i in range(32):
        if i == len(_gauges):
            break
        gauge: address = _gauges[i]
        votes: uint256 = available * _votes[i] / POINTS_SCALE

        if gauge != empty(address):
            assert self.gauge_whitelisted[gauge]
            self._update_gauge_emission(gauge)

        self.gauge_votes[epoch][gauge] += votes
        self.gauge_votes_user[msg.sender][epoch][gauge] += votes
        used += votes
        log Vote(epoch, msg.sender, gauge, votes)
    assert used > 0
    self.votes[epoch] += used

    used += self.votes_user[msg.sender][epoch]
    assert used <= available
    self.votes_user[msg.sender][epoch] = used

@external
def claim(_gauge: address = empty(address), _recipient: address = empty(address)) -> (uint256, uint256, uint256):
    """
    @notice Claim rewards for distribution by a gauge
    @param _gauge Gauge address to claim for
    @param _recipient Recipient of legacy gauge rewards
    @dev Certain gauges are considered legacy, for which claiming is permissioned
    """
    gauge: address = _gauge
    if _gauge == empty(address):
        gauge = msg.sender
    recipient: address = gauge

    if self.legacy_gauge[gauge]:
        assert msg.sender == self.legacy_operator
        assert _recipient != empty(address)
        recipient = _recipient

    assert self._update_emission()
    gauge_epoch: uint256 = 0
    cumulative: uint256 = 0
    current: uint256 = 0
    gauge_epoch, cumulative, current = self._update_gauge_emission(gauge)
    claimed: uint256 = self.gauge_claimed[gauge]
    claim: uint256 = cumulative - claimed
    if claim > 0:
        self.gauge_claimed[gauge] = cumulative
        assert token.transfer(recipient, claim, default_return_value=True)
        log Claim(_gauge, claim)

    epoch_start: uint256 = genesis + self._epoch() * EPOCH_LENGTH
    return cumulative, current, epoch_start

@external
def update_emission():
    """
    @notice Update overall emissions
    @dev Should be called by anyone to catch-up overall emissions if no 
        calls to this contract have been made for more than a full epoch
    """
    for _ in range(32):
        if self._update_emission():
            return

@external
def whitelist(_gauge: address, _whitelisted: bool):
    """
    @notice Add or remove a gauge to the whitelist
    @param _gauge Gauge address
    @param _whitelisted True: add to whitelist, False: remove from whitelist
    @dev Only callable by the whitelister
    """
    assert msg.sender == self.whitelister
    assert _gauge != empty(address)
    assert not self._vote_open()
    assert self._update_emission()

    if _whitelisted == self.gauge_whitelisted[_gauge]:
        return

    if not _whitelisted:
        self._update_gauge_emission(_gauge)
        points: uint256 = 0
        last: uint256 = 0
        points, last = self._unpack_two(self.packed_gauge_reserved[_gauge])
        if points > 0:
            self.reserved_points -= points
            self.packed_gauge_reserved[_gauge] = 0
    self.gauge_whitelisted[_gauge] = _whitelisted
    log Whitelist(_gauge, _whitelisted)

@external
def set_reserved_points(_gauge: address, _points: uint256):
    """
    @notice Set the fraction of reserved emissions for a gauge
    @param _gauge Gauge address
    @param _points Reserved emission fraction (bps)
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert self.gauge_whitelisted[_gauge]
    assert not self._vote_open()
    assert self._update_emission()

    self._update_gauge_emission(_gauge)
    prev_points: uint256 = 0
    last: uint256 = 0
    prev_points, last = self._unpack_two(self.packed_gauge_reserved[_gauge])
    if prev_points == 0:
        # to save gas the cumulative amount is never updated for gauges without 
        # reserved points, so we have to do it here
        last = self._unpack_two(self.packed_emission)[0]

    total_points: uint256 = self.reserved_points - prev_points + _points
    assert total_points <= POINTS_SCALE
    self.reserved_points = total_points
    self.packed_gauge_reserved[_gauge] = self._pack(0, _points, last)
    log SetReservedPoints(_gauge, _points)

@external
def set_blank_burn_points(_points: uint256):
    """
    @notice Set fraction of blank emissions to be burned
    @param _points Blank burn fraction (bps)
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _points <= POINTS_SCALE
    assert not self._vote_open()
    assert self._update_emission()
    self.blank_burn_points = _points
    log SetBlankBurnPoints(_points)

@external
def set_legacy_gauge(_gauge: address, _legacy: bool):
    """
    @notice Set legacy status for a gauge
    @param _gauge Gauge address
    @param _legacy True: legacy, False: no legacy
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert self.gauge_whitelisted[_gauge]
    self.legacy_gauge[_gauge] = _legacy
    log SetLegacyGauge(_gauge, _legacy)

@external
def set_whitelister(_whitelister: address):
    """
    @notice Set new whitelister address
    @param _whitelister New whitelister address
    @dev Only callable by management
    """
    assert msg.sender == self.management
    self.whitelister = _whitelister
    log SetWhitelister(_whitelister)

@external
def set_legacy_operator(_operator: address):
    """
    @notice Set new legacy operator
    @param _operator New operator address
    @dev Only callable by management
    """
    assert msg.sender == self.management
    self.legacy_operator = _operator
    log SetLegacyOperator(_operator)

@external
def set_measure(_measure: address):
    """
    @notice Set vote weight measure
    @param _measure Measure address
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _measure != empty(address)
    assert not self._vote_open()
    self.measure = Measure(_measure)
    log SetMeasure(_measure)

@external
def set_minter(_minter: address):
    """
    @notice Set new reward minter
    @param _minter New minter address
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _minter != empty(address)
    assert self._update_emission()
    self.minter = Minter(_minter)
    log SetMinter(_minter)

@external
def set_burner(_burner: address):
    """
    @notice Set new reward burner
    @param _burner New burner address
    @dev Only callable by management
    """
    assert msg.sender == self.management
    assert _burner != empty(address)
    assert self._update_emission()
    self.burner = Burner(_burner)
    log SetBurner(_burner)

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
def _update_emission() -> bool:
    """
    @notice 
        Update global emission. Must be called before:
            - Any gauge is updated
            - Any gauge receives votes
            - Any gauge reserved points is changed
            - Blank vote burn points is changed
    """

    last_epoch: uint256 = self._epoch() - 1
    global_epoch: uint256 = 0
    global_cumulative: uint256 = 0
    global_current: uint256 = 0
    global_epoch, global_cumulative, global_current = self._unpack(self.packed_emission)

    if global_epoch == last_epoch:
        return True
    global_epoch += 1

    minted: uint256 = self.minter.mint(global_epoch) + self.blank_emission
    reserved: uint256 = minted * self.reserved_points / POINTS_SCALE

    blank_votes: uint256 = self.gauge_votes[global_epoch][empty(address)]
    total_votes: uint256 = self.votes[global_epoch]
    blank_emission: uint256 = 0
    if blank_votes > 0:
        blank_emission = (minted - reserved) * blank_votes / total_votes
    elif total_votes == 0:
        # no votes: all non-reserved emissions are considered blank
        blank_emission = minted - reserved

    burn_amount: uint256 = 0
    if blank_emission > 0:
        # blank emission is partially burned and partially added to next epoch
        burn_amount = blank_emission * self.blank_burn_points / POINTS_SCALE
        if burn_amount > 0:
            blank_emission -= burn_amount
            assert token.approve(self.burner.address, burn_amount, default_return_value=True)
            self.burner.burn(global_epoch, burn_amount)

    global_cumulative += minted
    global_current = minted

    self.packed_emission = self._pack(global_epoch, global_cumulative, global_current)
    self.blank_emission = blank_emission
    self.packed_epoch_emission[global_epoch] = self._pack(0, minted, reserved)
    log NewEpoch(global_epoch, minted, reserved, burn_amount, blank_emission)
    return global_epoch == last_epoch
    
@internal
def _update_gauge_emission(_gauge: address) -> (uint256, uint256, uint256):
    """
    @notice 
        Update gauge emission. Must be called before:
            - Gauge receives votes
            - Gauge claim
            - Gauge reserved points changes
        Assumes global emission is up to date
    """

    last_epoch: uint256 = self._epoch() - 1

    gauge_epoch: uint256 = 0
    cumulative: uint256 = 0
    current: uint256 = 0
    gauge_epoch, cumulative, current = self._unpack(self.packed_gauge_emission[_gauge])

    if gauge_epoch == last_epoch:
        return gauge_epoch, cumulative, current

    # emission from last updated epoch
    last_updated_epoch: uint256 = gauge_epoch + 1
    current = self.gauge_votes[last_updated_epoch][_gauge]
    if current > 0:
        epoch_emission: uint256 = 0
        epoch_reserved: uint256 = 0
        epoch_emission, epoch_reserved = self._unpack_two(self.packed_epoch_emission[last_updated_epoch])
        current = (epoch_emission - epoch_reserved) * current / self.votes[last_updated_epoch]
        cumulative += current
        if last_updated_epoch != last_epoch:
            # last update was more than 1 epoch ago. the full amount is immediately available
            # we know the other missing epochs did not have any votes for this gauge because
            # the gauge emissions would have been updated
            current = 0

    # fast-forward reserved emission
    points: uint256 = 0
    last: uint256 = 0
    points, last = self._unpack_two(self.packed_gauge_reserved[_gauge])
    if points > 0:
        # we know that reserved points for this gauge has remained constant since the last 
        # gauge update, so we can safely get reserved rewards from potentially multiple epochs
        # by applying the points to the change in global cumulative emission
        global_cumulative: uint256 = 0
        global_current: uint256 = 0
        global_cumulative, global_current = self._unpack_two(self.packed_emission)
        
        current += global_current * points / POINTS_SCALE
        cumulative += (global_cumulative - last) * points / POINTS_SCALE
        self.packed_gauge_reserved[_gauge] = self._pack(0, points, global_cumulative)

    self.packed_gauge_emission[_gauge] = self._pack(last_epoch, cumulative, current)
    return last_epoch, cumulative, current

@internal
@pure
def _pack(_epoch: uint256, _a: uint256, _b: uint256) -> uint256:
    """
    @notice Pack a 32 bit number with two 112 bit numbers
    """
    assert _epoch <= EPOCH_MASK and _a <= MASK and _b <= MASK
    return (_epoch << 224) | (_a << 112) | _b

@internal
@pure
def _unpack(_packed: uint256) -> (uint256, uint256, uint256):
    """
    @notice Unpack a 32 bit number followed by two 112 bit numbers
    """
    return _packed >> 224, (_packed >> 112) & MASK, _packed & MASK

@internal
@pure
def _unpack_two(_packed: uint256) -> (uint256, uint256):
    """
    @notice Unpack last two 112 bit numbers
    """
    return (_packed >> 112) & MASK, _packed & MASK
