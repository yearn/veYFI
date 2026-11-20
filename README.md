[Governance spec](./GOVERNANCE.md)

## veYFI

veYFI is locking similar to the ve-style program of Curve. 

### Max lock

YFI can be locked up to 4 years into veYFI, which is non-transferable. They are at least locked for a week.

### veYFI balance

The duration of the lock gives the amount of veYFI relative to the amount locked, locking for four years gives you a veYFI balance equal to the amount of YFI locked. Locking for 2 years gives you a veYFI balance of 50% of the YFI locked.
The balance decay overtime and can be pushed back to max value by increasing the lock back to the max lock duration.


### veYFI early exit
It’s possible to exit the lock early, in exchange for paying a penalty that gets distributed to the account that have veYFI locked. The penalty for exiting early is the following: 
```
    min(75%, lock_duration_left / 4 years * 100%)
```
So at most you are paying a 75% penalty that starts decreasing when your lock duration goes beyond 3 years.

## Gauges

Gauges allow vault depositors to stake their vault tokens and earn dYFI rewards according to the amount of dYFI to be distributed and their veYFI weight.

### Gauges boosting

Gauge rewards are boosted with a max boost of 10x. The max boost is a variable that can be adjusted by the team.

The boost mechanism will calculate your earning weight by taking the smaller amount of two values:
- The first value is the amount of liquidity you are providing. This amount is your maximum earning weight.
- The second value is 10% of first value + 90% the amount deposited in gauge multiplied by the ratio of your `veYFI Balance/veYFI Total Supply`.
```
min(AmountDeposited, (AmountDeposited /10) + (TotalDepositedInTheGauge * VeYFIBalance / VeYFITotalSupply * 0.9))
```
When a user interacts with the gauge, the boosted amount is snapshotted until the next interaction.
The rewards that are not distributed because the balance isn't fully boosted are distributed back to veYFI holders.

### Gauge YFI distribution

Every two weeks veYFI holders can vote on dYFI distribution to gauges.

## veYFIRewardPool

Users who lock veYFI can claim YFI from the veYFI exited early and the non-distributed gauge rewards due to the lack of boost.
You will be able to start claiming from the veFYI reward pool two or three weeks from the Thursday after which you lock before you can claim.


## dYFIRewardPool

Users who lock veYFI can claim dYFI from the dYFI that aren't distributed due to the lack of boost.

## Redemption

Redemption is the contract used to redeem dYFI for YFI using ETH. YFI/ETH price is fetched from curve and chainlink oracles. YFI is sold at a discounted rate based on the ratio between the total YFI supply and the veYFI supply.

## Setup

Install ape framework. See [ape quickstart guide](https://docs.apeworx.io/ape/stable/userguides/quickstart.html)

Install dependencies
```bash
npm install
```

Install [Foundry](https://github.com/foundry-rs/foundry) for running tests
```bash
curl -L https://foundry.paradigm.xyz | bash
```

```bash
foundryup
```

## Compile

Install ape plugins
```bash
ape plugins install .
```

```bash
ape compile
```

## Test

```bash
ape test
```
