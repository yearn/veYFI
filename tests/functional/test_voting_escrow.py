from pytest import approx
import ape

H = 3600
DAY = 86400
WEEK = 7 * DAY
MAXTIME = 126144000
TOL = 120 / WEEK


def test_voting_powers(chain, accounts, yfi, ve_yfi):
    """
    Test voting power in the following scenario.
    Alice:
    ~~~~~~~
    ^
    | *       *
    | | \     |  \
    | |  \    |    \
    +-+---+---+------+---> t
    Bob:
    ~~~~~~~
    ^
    |         *
    |         | \
    |         |  \
    +-+---+---+---+--+---> t
    Alice has 100% of voting power in the first period.
    She has 2/3 power at the start of 2nd period, with Bob having 1/2 power
    (due to smaller locktime).
    Alice's power grows to 100% by Bob's unlock.
    Checking that totalSupply is appropriate.
    After the test is done, check all over again with balanceOfAt / totalSupplyAt
    """
    alice, bob = accounts[:2]
    amount = 1000 * 10**18
    yfi.mint(bob, amount, sender=bob)
    yfi.mint(alice, amount, sender=alice)

    stages = {}

    yfi.approve(ve_yfi.address, amount * 10, sender=alice)
    yfi.approve(ve_yfi.address, amount * 10, sender=bob)

    assert ve_yfi.totalSupply() == 0
    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.balanceOf(bob) == 0

    # Move to timing which is good for testing - beginning of a UTC week
    chain.pending_timestamp += (
        chain.blocks.head.timestamp // WEEK + 1
    ) * WEEK - chain.blocks.head.timestamp
    chain.mine()

    chain.pending_timestamp += H

    stages["before_deposits"] = (chain.blocks.head.number, chain.blocks.head.timestamp)

    ve_yfi.modify_lock(amount, chain.blocks.head.timestamp + WEEK, sender=alice)
    stages["alice_deposit"] = (chain.blocks.head.number, chain.blocks.head.timestamp)

    chain.pending_timestamp += H
    chain.mine()

    assert approx(ve_yfi.totalSupply(), amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert approx(ve_yfi.balanceOf(alice), amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert ve_yfi.balanceOf(bob) == 0
    t0 = chain.blocks.head.timestamp

    stages["alice_in_0"] = []
    stages["alice_in_0"].append((chain.blocks.head.number, chain.blocks.head.timestamp))
    for i in range(7):
        for _ in range(24):
            chain.pending_timestamp += H
            chain.mine()
        dt = chain.blocks.head.timestamp - t0
        assert approx(
            ve_yfi.totalSupply(),
            amount // MAXTIME * max(WEEK - 2 * H - dt, 0),
            TOL,
        )
        assert approx(
            ve_yfi.balanceOf(alice),
            amount // MAXTIME * max(WEEK - 2 * H - dt, 0),
            TOL,
        )
        assert ve_yfi.balanceOf(bob) == 0
        stages["alice_in_0"].append(
            (chain.blocks.head.number, chain.blocks.head.timestamp)
        )

    chain.pending_timestamp += H

    assert ve_yfi.balanceOf(alice) == 0
    ve_yfi.withdraw(sender=alice)
    stages["alice_withdraw"] = (chain.blocks.head.number, chain.blocks.head.timestamp)
    assert ve_yfi.totalSupply() == 0
    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.balanceOf(bob) == 0

    chain.pending_timestamp += H
    chain.mine()

    # Next week (for round counting)
    chain.pending_timestamp += (
        chain.blocks.head.timestamp // WEEK + 1
    ) * WEEK - chain.blocks.head.timestamp
    chain.mine()

    ve_yfi.modify_lock(amount, chain.blocks.head.timestamp + 2 * WEEK, sender=alice)
    stages["alice_deposit_2"] = (chain.blocks.head.number, chain.blocks.head.timestamp)

    assert approx(ve_yfi.totalSupply(), amount // MAXTIME * 2 * WEEK, TOL)
    assert approx(ve_yfi.balanceOf(alice), amount // MAXTIME * 2 * WEEK, TOL)
    assert ve_yfi.balanceOf(bob) == 0

    ve_yfi.modify_lock(amount, chain.blocks.head.timestamp + WEEK, sender=bob)
    stages["bob_deposit_2"] = (chain.blocks.head.number, chain.blocks.head.timestamp)

    assert approx(ve_yfi.totalSupply(), amount // MAXTIME * 3 * WEEK, TOL)
    assert approx(ve_yfi.balanceOf(alice), amount // MAXTIME * 2 * WEEK, TOL)
    assert approx(ve_yfi.balanceOf(bob), amount // MAXTIME * WEEK, TOL)

    t0 = chain.blocks.head.timestamp
    chain.pending_timestamp += H
    chain.mine()

    stages["alice_bob_in_2"] = []
    # Beginning of week: weight 3
    # End of week: weight 1
    for i in range(7):
        for _ in range(24):
            chain.pending_timestamp += H
            chain.mine()
        dt = chain.blocks.head.timestamp - t0
        w_total = ve_yfi.totalSupply()
        w_alice = ve_yfi.balanceOf(alice)
        w_bob = ve_yfi.balanceOf(bob)
        assert w_total == w_alice + w_bob
        assert approx(w_alice, amount // MAXTIME * max(2 * WEEK - dt, 0), TOL)
        assert approx(w_bob, amount // MAXTIME * max(WEEK - dt, 0), TOL)
        stages["alice_bob_in_2"].append(
            (chain.blocks.head.number, chain.blocks.head.timestamp)
        )

    chain.pending_timestamp += H
    chain.mine()

    ve_yfi.withdraw(sender=bob)
    t0 = chain.blocks.head.timestamp
    stages["bob_withdraw_1"] = (chain.blocks.head.number, chain.blocks.head.timestamp)
    w_total = ve_yfi.totalSupply()
    w_alice = ve_yfi.balanceOf(alice)
    assert w_alice == w_total
    assert approx(w_total, amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert ve_yfi.balanceOf(bob) == 0

    chain.pending_timestamp += H
    chain.mine()

    stages["alice_in_2"] = []
    for i in range(7):
        for _ in range(24):
            chain.pending_timestamp += H
            chain.mine()
        dt = chain.blocks.head.timestamp - t0
        w_total = ve_yfi.totalSupply()
        w_alice = ve_yfi.balanceOf(alice)
        assert w_total == w_alice
        assert approx(w_total, amount // MAXTIME * max(WEEK - dt - 2 * H, 0), TOL)
        assert ve_yfi.balanceOf(bob) == 0
        stages["alice_in_2"].append(
            (chain.blocks.head.number, chain.blocks.head.timestamp)
        )

    ve_yfi.withdraw(sender=alice)
    stages["alice_withdraw_2"] = (chain.blocks.head.number, chain.blocks.head.timestamp)

    chain.pending_timestamp += H
    chain.mine()

    ve_yfi.withdraw(sender=bob)
    stages["bob_withdraw_2"] = (chain.blocks.head.number, chain.blocks.head.timestamp)

    assert ve_yfi.totalSupply() == 0
    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.balanceOf(bob) == 0

    # Now test historical balanceOfAt and others

    assert ve_yfi.balanceOfAt(alice, stages["before_deposits"][0]) == 0
    assert ve_yfi.balanceOfAt(bob, stages["before_deposits"][0]) == 0
    assert ve_yfi.totalSupplyAt(stages["before_deposits"][0]) == 0

    w_alice = ve_yfi.balanceOfAt(alice, stages["alice_deposit"][0])
    assert approx(w_alice, amount // MAXTIME * (WEEK - H), TOL)
    assert ve_yfi.balanceOfAt(bob, stages["alice_deposit"][0]) == 0
    w_total = ve_yfi.totalSupplyAt(stages["alice_deposit"][0])
    assert w_alice == w_total

    for i, (block, t) in enumerate(stages["alice_in_0"]):
        w_alice = ve_yfi.balanceOfAt(alice, block)
        w_bob = ve_yfi.balanceOfAt(bob, block)
        w_total = ve_yfi.totalSupplyAt(block)
        assert w_bob == 0
        assert w_alice == w_total
        time_left = WEEK * (7 - i) // 7 - 2 * H
        error_1h = (
            H / time_left
        )  # Rounding error of 1 block is possible, and we have 1h blocks
        assert approx(w_alice, amount // MAXTIME * time_left, error_1h)

    w_total = ve_yfi.totalSupplyAt(stages["alice_withdraw"][0])
    w_alice = ve_yfi.balanceOfAt(alice, stages["alice_withdraw"][0])
    w_bob = ve_yfi.balanceOfAt(bob, stages["alice_withdraw"][0])
    assert w_alice == w_bob == w_total == 0

    w_total = ve_yfi.totalSupplyAt(stages["alice_deposit_2"][0])
    w_alice = ve_yfi.balanceOfAt(alice, stages["alice_deposit_2"][0])
    w_bob = ve_yfi.balanceOfAt(bob, stages["alice_deposit_2"][0])
    assert approx(w_total, amount // MAXTIME * 2 * WEEK, TOL)
    assert w_total == w_alice
    assert w_bob == 0

    w_total = ve_yfi.totalSupplyAt(stages["bob_deposit_2"][0])
    w_alice = ve_yfi.balanceOfAt(alice, stages["bob_deposit_2"][0])
    w_bob = ve_yfi.balanceOfAt(bob, stages["bob_deposit_2"][0])
    assert w_total == w_alice + w_bob
    assert approx(w_total, amount // MAXTIME * 3 * WEEK, TOL)
    assert approx(w_alice, amount // MAXTIME * 2 * WEEK, TOL)

    t0 = stages["bob_deposit_2"][1]
    for i, (block, t) in enumerate(stages["alice_bob_in_2"]):
        w_alice = ve_yfi.balanceOfAt(alice, block)
        w_bob = ve_yfi.balanceOfAt(bob, block)
        w_total = ve_yfi.totalSupplyAt(block)
        assert w_total == w_alice + w_bob
        dt = t - t0
        error_1h = H / (
            2 * WEEK - i * DAY
        )  # Rounding error of 1 block is possible, and we have 1h blocks
        assert approx(w_alice, amount // MAXTIME * max(2 * WEEK - dt, 0), error_1h)
        assert approx(w_bob, amount // MAXTIME * max(WEEK - dt, 0), error_1h)

    w_total = ve_yfi.totalSupplyAt(stages["bob_withdraw_1"][0])
    w_alice = ve_yfi.balanceOfAt(alice, stages["bob_withdraw_1"][0])
    w_bob = ve_yfi.balanceOfAt(bob, stages["bob_withdraw_1"][0])
    assert w_total == w_alice
    assert approx(w_total, amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert w_bob == 0

    t0 = stages["bob_withdraw_1"][1]
    for i, (block, t) in enumerate(stages["alice_in_2"]):
        w_alice = ve_yfi.balanceOfAt(alice, block)
        w_bob = ve_yfi.balanceOfAt(bob, block)
        w_total = ve_yfi.totalSupplyAt(block)
        assert w_total == w_alice
        assert w_bob == 0
        dt = t - t0
        error_1h = H / (
            WEEK - i * DAY + DAY
        )  # Rounding error of 1 block is possible, and we have 1h blocks
        assert approx(w_total, amount // MAXTIME * max(WEEK - dt - 2 * H, 0), error_1h)

    w_total = ve_yfi.totalSupplyAt(stages["bob_withdraw_2"][0])
    w_alice = ve_yfi.balanceOfAt(alice, stages["bob_withdraw_2"][0])
    w_bob = ve_yfi.balanceOfAt(bob, stages["bob_withdraw_2"][0])
    assert w_total == w_alice == w_bob == 0


def test_early_exit(chain, accounts, yfi, ve_yfi):
    alice, bob = accounts[:2]
    amount = 1000 * 10**18
    yfi.mint(bob, amount, sender=bob)
    yfi.mint(alice, amount, sender=alice)

    yfi.approve(ve_yfi.address, amount * 10, sender=alice)
    yfi.approve(ve_yfi.address, amount * 10, sender=bob)

    chain.pending_timestamp += (
        chain.blocks.head.timestamp // WEEK + 1
    ) * WEEK - chain.blocks.head.timestamp
    chain.mine()

    chain.pending_timestamp += H
    ve_yfi.modify_lock(amount, chain.blocks.head.timestamp + 2 * WEEK, sender=alice)
    ve_yfi.modify_lock(amount, chain.blocks.head.timestamp + WEEK, sender=bob)
    ve_yfi.withdraw(sender=bob)
    assert ve_yfi.totalSupply() == ve_yfi.balanceOf(alice)

    point_history_1 = dict(
        zip(["bias", "slope", "ts", "blk"], ve_yfi.point_history(ve_yfi, 1))
    )
    point_history_3 = dict(
        zip(["bias", "slope", "ts", "blk"], ve_yfi.point_history(ve_yfi, 3))
    )
    assert approx(point_history_1["bias"], rel=10e-4) == point_history_3["bias"]
    assert approx(point_history_1["slope"], rel=10e-4) == point_history_3["slope"]
    ve_yfi.withdraw(sender=alice)
    assert ve_yfi.totalSupply() == 0
    point_history_4 = dict(
        zip(["bias", "slope", "ts", "blk"], ve_yfi.point_history(ve_yfi, 4))
    )
    assert point_history_4["ts"] == chain.blocks.head.timestamp
    assert point_history_4["bias"] == 0
    assert point_history_4["slope"] == 0
