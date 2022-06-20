# Voting YFI

This contract is partially derived from [Curve's Voting Escrow](https://github.com/curvefi/curve-dao-contracts/blob/master/contracts/VotingEscrow.vy)

## Locks
- A user can lock YFI for any duration.
- A user can create a lock with at least 1 YFI.
- Nobody can create a lock for another user.
- A user can deposit an additional amount to their existing lock.
- Anybody can deposit an additional amount to anyone's existing lock.
- A user can increase the lock end time to any time in the future.
- Nobody except the user can alter the lock duration for a user.
- A user can decrease the lock duration but only if it's longer than 4 years and to no less than 4 years.
- A user can deposit and additional amount and modify the duration following the rules above as one action.
- Lock end times are rounded to a week.

## Voting power
- A user's voting power is linearly decreasing and capped at 4 years remaining lock time.
- If a user's lock has over 4 years till expiration, their voting power is constant and equal to the max power of 1 YFI = 1 veYFI.
- A user can withdraw YFI after their lock has expired.
- A user can withdraw YFI before their lock has expired, suffering a penalty.
- A penalty is a linear function of a remaining lock time, capped at 75%, so it's a constant 75% penalty from 3 to 4 years remaining.
- A penalty is sent to the Reward Pool and queued using the `burn()` call.

# Reward Pool

This contract is partially derived from [Curve's Fee Distributor](https://github.com/curvefi/curve-dao-contracts/blob/master/contracts/FeeDistributor.vy)
