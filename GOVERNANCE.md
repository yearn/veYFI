## veYFI governance

### Gauge factory
- Used for permissionless deployment of gauge for any vault
- Gauge is minimal immutable proxy pointing to gauge implementation
- Management can change:
    - gauge implementation
    - gauge controller
    - gauge owner
- Changes in these parameters only affects future deployments
- Factory keeps track of gauges originating from it and the used version
- Before setting an initial gauge implementation, management can mark legacy gauges as originating from the vault
- Legacy gauges will have version 1

### Gauge registry
- Keeps track of registered gauges and vaults
- Only one gauge can be registered per vault
- Management can register and deregister gauges
- On registration the gauge has to originate from the current configured factory
- On registration the gauge will be added to the whitelist in the gauge controller
- On deregistration the gauge will be removed from the whitelist in the gauge controller
- Management can change:
    - gauge controller
    - gauge factory

### Gauge controller
- Controls emission of rewards (dYFI) to gauges
- Gauges can be whitelisted, enabling potential future emissions
- Once per 2-week epoch, users with a vote weight can distribute their votes over the whitelisted gauges
- Voting is enabled in the second week of the epoch
- Vote weight for each user is determined by a 'vote weight measure'
- Votes can be 'blank'. Any rewards resulting of those votes are partially burned and partially preserved for next epoch. The ratio between burned and preserved is configurable
- A fixed percentage of emissions can be reserved for specific gauges. The remaining non-reserved emissions are distributed according to their received voting weight
- The configured minter is responsible for determining the amount of rewards per epoch and transfering them to the controller
- After an epoch the controller will invoke the minter and receive the rewards
- After an epoch rewards can be claimed to the gauges, aimed to be streamed out over the following epoch to the gauge depositors
- Gauges can be marked as 'legacy', making the reward claim permissioned by the operator
- If gauge rewards have not been claimed for multiple epochs, they will all be transferred at the first claim
- Controller tracks cumulative reward per gauge as well as the reward in the current epoch
- Whitelister can add and remove gauges from whitelisting 
    - only outside of voting period
    - removes reserved points from gauge too
- Management can change:
    - whitelister
    - vote weight measure
    - minter
    - reserved points (oustide of voting period)
    - blank burn points (outside of voting period)
    - gauge legacy status
    - operator

### Measure + DecayMeasure
- Vote weight equals the user's veYFI balance at start of vote
- Weight decays linearly to 0 in the last 24 hours of the epoch

### Minter
- Calculates and stores the emission of reward token for every epoch
- The emission associated with epoch `n`, to be distributed in epoch `n+1` by the gauges, is calculated as `c * sqrt(veYFI supply) * 14 / 365` where `c` is a configurable scaling factor and `veYFI supply` is evaluated at the end of the epoch
- Mints the emission to the gauge controller
- Management can:
    - change the scaling factor
    - change the gauge controller
    - transfer out ownership of the reward token

### GaugeV2
- Modified from V1 gauge
- In V1, `queueNewRewards` had to be called to start a new epoch, requiring timed manual interactions
- In V2, the gauge claims rewards from the controller. Even if there have been no interactions with the gauge for multiple epochs the rewards will be distributed appropriately upon interaction, whether its a user reward claim, deposit, withdraw, gauge token transfer etc

### BuybackAuction
- Contract runs permissionless dutch auctions to buy `want` tokens with ETH
- Auctions last 3 days or until the ETH runs out
- Any ETH left over at the end of the auction is rolled over to the next auction
- Any ETH deposited during an auction is not immediately available, it will be saved for the next auction
- Anyone can kick off an auction, provided there is ETH available and it has been at least 7 days since the last kick
- Auctions start at a price of `40_000 / (ETH amount available)` of `want` per ETH
- Price halves every hour with 1 minute granularity
- Anyone can take all or part of the remaining ETH amount in exchange for `want` at the current price
- Contract will automatically kick off an auction if a deposit puts the balance over a threshold value
- Any bought back `want` will be sent to the treasury
- Management can change:
    - treasury address
    - auto-kick threshold

### OwnershipProxy + Executor
- Copied from `yETH-periphery`, previously audited by ChainSecurity

### GenericGovernor
- Copied from `yETH-periphery`, previously audited by ChainSecurity
- Adjusted epoch length
- Added abstain votes which do not count for pass/fail but do count towards quorum
- Added IPFS CID to proposals
