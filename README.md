# veYFI

- Locking similar to the ve-style program of Curve.
- YFI can be locked up to 4 years into veYFI, which is non-transferable.
- The maximum lock duration is still tbd, but will be in the range of min 1 year, max 4 years.
- Locking duration gives the same linear weights, so if max duration is 4 years, this is 100%, and 2 years = 50% etc.
- Weights decay as the remaining lock duration decreases, and can be extended up to the max lock duration.
- Replaces xYFI, where a user must have a veYFI lock in order to continue to earn rewards. No lock leads to no rewards. Maximum lock, continuously renewed, maximizes rewards.
- It’s possible to exit the lock early, in exchange for paying a penalty that gets allocated to the other veYFI holders.
- Penalty size may be fixed (i.e. 50%), or may be depending on the remaining lock duration.


- Vault gauges allow vault depositors to stake their vault tokens and earn YFI rewards according to their veYFI weight.
- YFI are allocated to gauges based on weekly governance votes. Each gauge can get a different amount of bought back YFI to emit.
- Based on their veYFI lock, users can boost their rewards of up to 2.5x proportional to the amount of vault tokens deposited, when they claim YFI rewards from gauges. The greater the amount of veYFI, the more vault deposits can be boosted for the user.
- Inspired by Andre Cronje’s initial design of Fixed Forex[10], in order for gauge rewards to be claimed, the user must have a veYFI lock. Depending on their lock duration, they are entitled to a different share of gauge rewards: if max lock = 4 years, and user is locked for 4 years, they are entitled to 100% of their rewards, if user is locked for 2 years = 50% of rewards, if user has no lock = 0% of their rewards. The difference is paid as penalty to veYFI holders, as an additional source of yield.
- 
![03-gauges](https://user-images.githubusercontent.com/87183122/152998641-39c8454d-4cfe-4440-b497-12f3b4d83754.svg)


# Setup

See [brownie setup](https://eth-brownie.readthedocs.io/en/stable/install.html)

# Test

```
brownie test
```
