# @version 0.3.10
"""
@title Generic governor
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
@notice
    Governor for executing arbitrary calls, after passing through a voting procedure.
    Time is divided in 2 week epochs. During the first week, accounts with sufficient
    voting weight are able to submit proposals. In the final week of the epoch all accounts
    are able to vote on all open proposals. If at the end of the epoch the proposal has reached
    a sufficiently high fraction of votes, the proposal has passed and can be enacted through
    the executor.

    Most parameters are configurable by management. The management role is intended to be 
    transferred to the proxy, making the system self-governing.
"""

interface Measure:
    def vote_weight(_account: address) -> uint256: view

interface Executor:
    def execute(_script: Bytes[2048]): nonpayable

struct Proposal:
    epoch: uint256
    author: address
    ipfs: bytes32
    state: uint256
    hash: bytes32
    yea: uint256
    nay: uint256
    abstain: uint256

genesis: public(immutable(uint256))

management: public(address)
pending_management: public(address)

measure: public(address)
executor: public(address)
packed_quorum: uint256 # current (120) | previous (120) | epoch (16)
packed_majority: uint256 # current (120) | previous (120) | epoch (16)
packed_delay: uint256 # current (120) | previous (120) | epoch (16)
propose_min_weight: public(uint256)

num_proposals: public(uint256)
proposals: HashMap[uint256, Proposal]
voted: public(HashMap[address, HashMap[uint256, bool]])

event Propose:
    idx: indexed(uint256)
    epoch: indexed(uint256)
    author: indexed(address)
    ipfs: bytes32
    script: Bytes[2048]

event Retract:
    idx: indexed(uint256)

event Cancel:
    idx: indexed(uint256)

event Vote:
    account: indexed(address)
    idx: indexed(uint256)
    yea: uint256
    nay: uint256
    abstain: uint256

event Enact:
    idx: indexed(uint256)
    by: indexed(address)

event SetMeasure:
    measure: indexed(address)

event SetExecutor:
    executor: indexed(address)

event SetDelay:
    delay: uint256

event SetQuorum:
    quorum: uint256

event SetMajority:
    majority: uint256

event SetProposeMinWeight:
    min_weight: uint256

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

STATE_ABSENT: constant(uint256)    = 0
STATE_PROPOSED: constant(uint256)  = 1
STATE_PASSED: constant(uint256)    = 2
STATE_REJECTED: constant(uint256)  = 3
STATE_RETRACTED: constant(uint256) = 4
STATE_CANCELLED: constant(uint256) = 5
STATE_ENACTED: constant(uint256)   = 6

WEEK: constant(uint256) = 7 * 24 * 60 * 60
EPOCH_LENGTH: constant(uint256) = 2 * WEEK
VOTE_LENGTH: constant(uint256) = WEEK
VOTE_START: constant(uint256) = VOTE_LENGTH
VOTE_SCALE: constant(uint256) = 10_000

VALUE_MASK: constant(uint256) = 2**120 - 1
PREVIOUS_SHIFT: constant(int128) = -120
EPOCH_MASK: constant(uint256) = 2**16 - 1
EPOCH_SHIFT: constant(int128) = -240

@external
def __init__(_genesis: uint256, _measure: address, _executor: address, _quorum: uint256, _majority: uint256, _delay: uint256):
    """
    @notice Constructor
    @param _genesis Timestamp of start of epoch 0
    @param _measure Vote weight measure
    @param _executor Governance executor
    @param _quorum Quorum threshold (18 decimals)
    @param _majority Majority threshold (bps)
    @param _delay Vote enactment delay (seconds)
    """
    assert _genesis <= block.timestamp
    assert _measure != empty(address)
    assert _executor != empty(address)
    assert _quorum <= VALUE_MASK
    assert _majority >= VOTE_SCALE / 2 and _majority <= VOTE_SCALE
    assert _delay <= VOTE_START

    genesis = _genesis
    self.management = msg.sender
    self.measure = _measure
    self.executor = _executor
    self.packed_quorum = _quorum
    self.packed_majority = _majority
    self.packed_delay = _delay
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
    """
    @notice Get the current epoch
    """
    return (block.timestamp - genesis) / EPOCH_LENGTH

@external
@view
def propose_open() -> bool:
    """
    @notice Query whether the proposal period is currently open
    @return True: proposal period is open, False: proposal period is closed
    """
    return self._propose_open()

@internal
@view
def _propose_open() -> bool:
    """
    @notice Query whether the proposal period is currently open
    """
    return (block.timestamp - genesis) % EPOCH_LENGTH < VOTE_START

@external
@view
def vote_open() -> bool:
    """
    @notice Query whether the vote period is currently open
    @return True: vote period is open, False: vote period is closed
    """
    return self._vote_open()

@internal
@view
def _vote_open() -> bool:
    """
    @notice Query whether the vote period is currently open
    """
    return (block.timestamp - genesis) % EPOCH_LENGTH >= VOTE_START

@external
@view
def quorum() -> uint256:
    """
    @notice 
        Get quorum threshold. At least this voting weight must be used
        on a proposal for it to pass
    @return Quorum threshold (18 decimals)
    """
    return self.packed_quorum & VALUE_MASK

@external
@view
def previous_quorum() -> uint256:
    """
    @notice Get quorum threshold required to pass a proposal of previous epoch
    @return Quorum threshold (18 decimals)
    """
    return self._quorum(self._epoch() - 1)

@external
@view
def majority() -> uint256:
    """
    @notice Get majority threshold required to pass a proposal
    @return Majority threshold (bps)
    """
    return self.packed_majority & VALUE_MASK

@external
@view
def previous_majority() -> uint256:
    """
    @notice Get majority threshold required to pass a proposal of previous epoch
    @return Majority threshold (bps)
    """
    return self._majority(self._epoch() - 1)

@internal
@view
def _quorum(_epoch: uint256) -> uint256:
    """
    @notice Get quorum threshold of an epoch
    @param _epoch Epoch to query quorum threshold for
    @return Quorum threshold (18 decimals)
    @dev Should only be used to query this or last epoch's value
    """
    packed: uint256 = self.packed_quorum
    if _epoch < shift(packed, EPOCH_SHIFT):
        return shift(packed, PREVIOUS_SHIFT) & VALUE_MASK
    return packed & VALUE_MASK

@internal
@view
def _majority(_epoch: uint256) -> uint256:
    """
    @notice Get majority threshold of an epoch
    @param _epoch Epoch to query majority threshold for
    @return Majority threshold (bps)
    @dev Should only be used to query this or last epoch's value
    """
    packed: uint256 = self.packed_majority
    if _epoch < shift(packed, EPOCH_SHIFT):
        return shift(packed, PREVIOUS_SHIFT) & VALUE_MASK
    return packed & VALUE_MASK

@external
@view
def delay() -> uint256:
    """
    @notice Get minimum delay between passing a proposal and its enactment
    @return Enactment delay (seconds)
    """
    return self.packed_delay & VALUE_MASK

@external
@view
def previous_delay() -> uint256:
    """
    @notice Get minimum delay between passing a proposal and its enactment of previous epoch
    @return Enactment delay (seconds)
    """
    return self._delay(self._epoch() - 1)

@internal
@view
def _delay(_epoch: uint256) -> uint256:
    """
    @notice Get minimum delay between passing a proposal and its enactment
    @param _epoch Epoch to query delay for
    @return Enactment delay (seconds)
    @dev Should only be used to query this or last epoch's value
    """
    packed: uint256 = self.packed_delay
    if _epoch < shift(packed, EPOCH_SHIFT):
        return shift(packed, PREVIOUS_SHIFT) & VALUE_MASK
    return packed & VALUE_MASK

@external
@view
def proposal(_idx: uint256) -> Proposal:
    """
    @notice Get a proposal
    @param _idx Proposal index
    @return The proposal
    """
    proposal: Proposal = self.proposals[_idx]
    proposal.state = self._proposal_state(_idx)
    return proposal

@external
@view
def proposal_state(_idx: uint256) -> uint256:
    """
    @notice Get the state of a proposal
    @param _idx Proposal index
    @return The proposal state
    """
    return self._proposal_state(_idx)

@external
def update_proposal_state(_idx: uint256) -> uint256:
    """
    @notice Update the state of a proposal
    @param _idx Proposal index
    @return The proposal state
    """
    state: uint256 = self._proposal_state(_idx)
    if state != STATE_ABSENT:
        self.proposals[_idx].state = state
    return state

@internal
@view
def _proposal_state(_idx: uint256) -> uint256:
    """
    @notice Get the state of a proposal
    @dev Determines the pass/reject state based on the relative number of votes in favor
    """
    state: uint256 = self.proposals[_idx].state
    if state not in [STATE_PROPOSED, STATE_PASSED]:
        return state

    current_epoch: uint256 = self._epoch()
    vote_epoch: uint256 = self.proposals[_idx].epoch
    if current_epoch == vote_epoch:
        return STATE_PROPOSED
    
    if current_epoch == vote_epoch + 1:
        yea: uint256 = self.proposals[_idx].yea
        nay: uint256 = self.proposals[_idx].nay
        abstain: uint256 = self.proposals[_idx].abstain

        counted: uint256 = yea + nay # for majority purposes
        total: uint256 = counted + abstain # for quorum purposes
        if counted > 0 and total >= self._quorum(vote_epoch) and \
            yea * VOTE_SCALE >= counted * self._majority(vote_epoch):
            return STATE_PASSED

    return STATE_REJECTED

@external
def propose(_ipfs: bytes32, _script: Bytes[2048]) -> uint256:
    """
    @notice Create a proposal
    @param _ipfs IPFS CID containing a description of the proposal
    @param _script Script to be executed if the proposal passes
    @return The proposal index
    """
    assert self._propose_open()
    assert Measure(self.measure).vote_weight(msg.sender) >= self.propose_min_weight

    epoch: uint256 = self._epoch()
    idx: uint256 = self.num_proposals
    self.num_proposals = idx + 1
    self.proposals[idx].epoch = epoch
    self.proposals[idx].author = msg.sender
    self.proposals[idx].ipfs = _ipfs
    self.proposals[idx].state = STATE_PROPOSED
    self.proposals[idx].hash = keccak256(_script)
    log Propose(idx, epoch, msg.sender, _ipfs, _script)
    return idx

@external
def retract(_idx: uint256):
    """
    @notice Retract a proposal. Only callable by proposal author
    @param _idx Proposal index
    """
    assert msg.sender == self.proposals[_idx].author
    state: uint256 = self._proposal_state(_idx)
    assert state == STATE_PROPOSED and not self._vote_open()
    self.proposals[_idx].state = STATE_RETRACTED
    log Retract(_idx)

@external
def cancel(_idx: uint256):
    """
    @notice Cancel a proposal. Only callable by management
    @param _idx Proposal index
    """
    assert msg.sender == self.management
    state: uint256 = self._proposal_state(_idx)
    assert state == STATE_PROPOSED or state == STATE_PASSED
    self.proposals[_idx].state = STATE_CANCELLED
    log Cancel(_idx)

@external
def vote_yea(_idx: uint256):
    """
    @notice Vote in favor of a proposal
    @param _idx Proposal index
    """
    self._vote(_idx, VOTE_SCALE, 0, 0)

@external
def vote_nay(_idx: uint256):
    """
    @notice Vote in opposition of a proposal
    @param _idx Proposal index
    """
    self._vote(_idx, 0, VOTE_SCALE, 0)

@external
def vote_abstain(_idx: uint256):
    """
    @notice Vote in abstention of a proposal
    @param _idx Proposal index
    """
    self._vote(_idx, 0, 0, VOTE_SCALE)

@external
def vote(_idx: uint256, _yea: uint256, _nay: uint256, _abstain: uint256):
    """
    @notice Weighted vote on a proposal
    @param _idx Proposal index
    @param _yea Fraction of votes in favor
    @param _nay Fraction of votes in opposition
    @param _abstain Fraction of abstained votes
    """
    self._vote(_idx, _yea, _nay, _abstain)

@internal
def _vote(_idx: uint256, _yea: uint256, _nay: uint256, _abstain: uint256):
    """
    @notice Weighted vote on a proposal
    """
    assert self._vote_open()
    assert self.proposals[_idx].epoch == self._epoch()
    assert self.proposals[_idx].state == STATE_PROPOSED
    assert not self.voted[msg.sender][_idx]
    assert _yea + _nay + _abstain == VOTE_SCALE

    weight: uint256 = Measure(self.measure).vote_weight(msg.sender)
    assert weight > 0
    self.voted[msg.sender][_idx] = True
    yea: uint256 = 0
    if _yea > 0:
        yea = weight * _yea / VOTE_SCALE
        self.proposals[_idx].yea += yea
    nay: uint256 = 0
    if _nay > 0:
        nay = weight * _nay / VOTE_SCALE
        self.proposals[_idx].nay += nay
    abstain: uint256 = 0
    if _abstain > 0:
        abstain = weight * _abstain / VOTE_SCALE
        self.proposals[_idx].abstain += abstain
    log Vote(msg.sender, _idx, yea, nay, abstain)

@external
def enact(_idx: uint256, _script: Bytes[2048]):
    """
    @notice Enact a proposal after its vote has passed
    @param _idx Proposal index
    @param _script The script to execute
    """
    assert self._proposal_state(_idx) == STATE_PASSED
    assert keccak256(_script) == self.proposals[_idx].hash
    delay: uint256 = self._delay(self._epoch() - 1)
    assert (block.timestamp - genesis) % EPOCH_LENGTH >= delay

    self.proposals[_idx].state = STATE_ENACTED
    log Enact(_idx, msg.sender)
    Executor(self.executor).execute(_script)

@external
def set_measure(_measure: address):
    """
    @notice Set vote weight measure contract
    @param _measure New vote weight measure
    """
    assert msg.sender == self.management
    assert _measure != empty(address)
    self.measure = _measure
    log SetMeasure(_measure)

@external
def set_executor(_executor: address):
    """
    @notice Set executor contract
    @param _executor New executor
    """
    assert msg.sender == self.management
    assert _executor != empty(address)
    self.executor = _executor
    log SetExecutor(_executor)

@external
def set_quorum(_quorum: uint256):
    """
    @notice 
        Set quorum threshold in 18 decimals. 
        Proposals need at least this absolute number of votes to pass
    @param _quorum New quorum threshold (18 decimals)
    """
    assert msg.sender == self.management
    assert _quorum <= VALUE_MASK
    epoch: uint256 = self._epoch()
    previous: uint256 = self._quorum(epoch - 1)
    self.packed_quorum = _quorum | shift(previous, -PREVIOUS_SHIFT) | shift(epoch, -EPOCH_SHIFT)
    log SetQuorum(_quorum)

@external
def set_majority(_majority: uint256):
    """
    @notice 
        Set majority threshold in basispoints. 
        Proposals need at least this fraction of votes in favor to pass
    @param _majority New majority threshold (bps)
    """
    assert msg.sender == self.management
    assert _majority >= VOTE_SCALE / 2 and _majority <= VOTE_SCALE
    epoch: uint256 = self._epoch()
    previous: uint256 = self._majority(epoch - 1)
    self.packed_majority = _majority | shift(previous, -PREVIOUS_SHIFT) | shift(epoch, -EPOCH_SHIFT)
    log SetMajority(_majority)

@external
def set_delay(_delay: uint256):
    """
    @notice
        Set enactment time delay in seconds. Proposals that passed need to wait 
        at least this time before they can be enacted.
    @param _delay New delay (seconds)
    """
    assert msg.sender == self.management
    assert _delay <= VOTE_START
    epoch: uint256 = self._epoch()
    previous: uint256 = self._delay(epoch - 1)
    self.packed_delay = _delay | shift(previous, -PREVIOUS_SHIFT) | shift(epoch, -EPOCH_SHIFT)
    log SetDelay(_delay)

@external
def set_propose_min_weight(_propose_min_weight: uint256):
    """
    @notice Set minimum vote weight required to submit new proposals
    @param _propose_min_weight New minimum weight
    """
    assert msg.sender == self.management
    self.propose_min_weight = _propose_min_weight
    log SetProposeMinWeight(_propose_min_weight)

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
