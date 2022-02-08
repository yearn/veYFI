# veYFI

- Locking similar to the ve-style program of Curve.
- YFI can be locked up to 4 years into veYFI, which is non-transferable.
- The maximum lock duration is still tbd, but will be in the range of min 1 year, max 4 years.
- Locking duration gives the same linear weights, so if max duration is 4 years, this is 100%, and 2 years = 50% etc.
- Weights decay as the remaining lock duration decreases, and can be extended up to the max lock duration.
- Replaces xYFI, where a user must have a veYFI lock in order to continue to earn rewards. No lock leads to no rewards. Maximum lock, continuously renewed, maximizes rewards.
- It’s possible to exit the lock early, in exchange for paying a penalty that gets allocated to the other veYFI holders.
- Penalty size may be fixed (i.e. 50%), or may be depending on the remaining lock duration.


![image](https://user-images.githubusercontent.com/87183122/151378637-da78ca62-1f69-430b-abb4-a1b4e5665f33.png)

# Setup

See [brownie setup](https://eth-brownie.readthedocs.io/en/stable/install.html)

# Test

```
brownie test
```
