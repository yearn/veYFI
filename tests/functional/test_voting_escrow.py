from pytest import approx
import brownie

H = 3600
DAY = 86400
WEEK = 7 * DAY
MAXTIME = 126144000
TOL = 120 / WEEK


def test_voting_powers(web3, chain, accounts, yfi, ve_yfi, ve_yfi_rewards):
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
    yfi.mint(bob, amount, {"from": bob})
    yfi.mint(alice, amount, {"from": alice})

    stages = {}

    yfi.approve(ve_yfi.address, amount * 10, {"from": alice})
    yfi.approve(ve_yfi.address, amount * 10, {"from": bob})

    assert ve_yfi.totalSupply() == 0
    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.balanceOf(bob) == 0

    # Move to timing which is good for testing - beginning of a UTC week
    chain.sleep((chain[-1].timestamp // WEEK + 1) * WEEK - chain[-1].timestamp)
    chain.mine()

    chain.sleep(H)

    stages["before_deposits"] = (web3.eth.blockNumber, chain[-1].timestamp)

    ve_yfi.create_lock(amount, chain[-1].timestamp + WEEK, {"from": alice})
    stages["alice_deposit"] = (web3.eth.blockNumber, chain[-1].timestamp)

    chain.sleep(H)
    chain.mine()

    assert approx(ve_yfi.totalSupply(), amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert approx(ve_yfi.balanceOf(alice), amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert ve_yfi.balanceOf(bob) == 0
    t0 = chain[-1].timestamp

    stages["alice_in_0"] = []
    stages["alice_in_0"].append((web3.eth.blockNumber, chain[-1].timestamp))
    for i in range(7):
        for _ in range(24):
            chain.sleep(H)
            chain.mine()
        dt = chain[-1].timestamp - t0
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
        stages["alice_in_0"].append((web3.eth.blockNumber, chain[-1].timestamp))

    chain.sleep(H)

    assert ve_yfi.balanceOf(alice) == 0
    ve_yfi.withdraw({"from": alice})
    stages["alice_withdraw"] = (web3.eth.blockNumber, chain[-1].timestamp)
    assert ve_yfi.totalSupply() == 0
    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.balanceOf(bob) == 0

    chain.sleep(H)
    chain.mine()

    # Next week (for round counting)
    chain.sleep((chain[-1].timestamp // WEEK + 1) * WEEK - chain[-1].timestamp)
    chain.mine()

    ve_yfi.create_lock(amount, chain[-1].timestamp + 2 * WEEK, {"from": alice})
    stages["alice_deposit_2"] = (web3.eth.blockNumber, chain[-1].timestamp)

    assert approx(ve_yfi.totalSupply(), amount // MAXTIME * 2 * WEEK, TOL)
    assert approx(ve_yfi.balanceOf(alice), amount // MAXTIME * 2 * WEEK, TOL)
    assert ve_yfi.balanceOf(bob) == 0

    ve_yfi.create_lock(amount, chain[-1].timestamp + WEEK, {"from": bob})
    stages["bob_deposit_2"] = (web3.eth.blockNumber, chain[-1].timestamp)

    assert approx(ve_yfi.totalSupply(), amount // MAXTIME * 3 * WEEK, TOL)
    assert approx(ve_yfi.balanceOf(alice), amount // MAXTIME * 2 * WEEK, TOL)
    assert approx(ve_yfi.balanceOf(bob), amount // MAXTIME * WEEK, TOL)

    t0 = chain[-1].timestamp
    chain.sleep(H)
    chain.mine()

    stages["alice_bob_in_2"] = []
    # Beginning of week: weight 3
    # End of week: weight 1
    for i in range(7):
        for _ in range(24):
            chain.sleep(H)
            chain.mine()
        dt = chain[-1].timestamp - t0
        w_total = ve_yfi.totalSupply()
        w_alice = ve_yfi.balanceOf(alice)
        w_bob = ve_yfi.balanceOf(bob)
        assert w_total == w_alice + w_bob
        assert approx(w_alice, amount // MAXTIME * max(2 * WEEK - dt, 0), TOL)
        assert approx(w_bob, amount // MAXTIME * max(WEEK - dt, 0), TOL)
        stages["alice_bob_in_2"].append((web3.eth.blockNumber, chain[-1].timestamp))

    chain.sleep(H)
    chain.mine()

    ve_yfi.withdraw({"from": bob})
    t0 = chain[-1].timestamp
    stages["bob_withdraw_1"] = (web3.eth.blockNumber, chain[-1].timestamp)
    w_total = ve_yfi.totalSupply()
    w_alice = ve_yfi.balanceOf(alice)
    assert w_alice == w_total
    assert approx(w_total, amount // MAXTIME * (WEEK - 2 * H), TOL)
    assert ve_yfi.balanceOf(bob) == 0

    chain.sleep(H)
    chain.mine()

    stages["alice_in_2"] = []
    for i in range(7):
        for _ in range(24):
            chain.sleep(H)
            chain.mine()
        dt = chain[-1].timestamp - t0
        w_total = ve_yfi.totalSupply()
        w_alice = ve_yfi.balanceOf(alice)
        assert w_total == w_alice
        assert approx(w_total, amount // MAXTIME * max(WEEK - dt - 2 * H, 0), TOL)
        assert ve_yfi.balanceOf(bob) == 0
        stages["alice_in_2"].append((web3.eth.blockNumber, chain[-1].timestamp))

    ve_yfi.withdraw({"from": alice})
    stages["alice_withdraw_2"] = (web3.eth.blockNumber, chain[-1].timestamp)

    chain.sleep(H)
    chain.mine()

    ve_yfi.withdraw({"from": bob})
    stages["bob_withdraw_2"] = (web3.eth.blockNumber, chain[-1].timestamp)

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


def test_early_exit(web3, chain, accounts, yfi, ve_yfi, ve_yfi_rewards):
    alice, bob = accounts[:2]
    amount = 1000 * 10**18
    yfi.mint(bob, amount, {"from": bob})
    yfi.mint(alice, amount, {"from": alice})

    yfi.approve(ve_yfi.address, amount * 10, {"from": alice})
    yfi.approve(ve_yfi.address, amount * 10, {"from": bob})

    chain.sleep((chain[-1].timestamp // WEEK + 1) * WEEK - chain[-1].timestamp)
    chain.mine()

    chain.sleep(H)
    ve_yfi.create_lock(amount, chain[-1].timestamp + 2 * WEEK, {"from": alice})
    ve_yfi.create_lock(amount, chain[-1].timestamp + WEEK, {"from": bob})
    ve_yfi.force_withdraw({"from": bob})
    assert ve_yfi.totalSupply() == ve_yfi.balanceOf(alice)

    point_history_1 = ve_yfi.point_history(1).dict()
    point_history_3 = ve_yfi.point_history(3).dict()
    assert approx(point_history_1["bias"], rel=10e-4) == point_history_3["bias"]
    assert approx(point_history_1["slope"], rel=10e-4) == point_history_3["slope"]
    ve_yfi.force_withdraw({"from": alice})
    assert ve_yfi.totalSupply() == 0
    point_history_4 = ve_yfi.point_history(4).dict()
    assert point_history_4["ts"] == chain[-1].timestamp
    assert point_history_4["bias"] == 0
    assert point_history_4["slope"] == 0


def test_migrate_set_balance_to_zero(
    web3, chain, accounts, yfi, ve_yfi, ve_yfi_rewards, gov, NextVe
):
    alice, bob = accounts[:2]
    amount = 1000 * 10**18
    yfi.mint(bob, amount, {"from": bob})
    yfi.mint(alice, amount, {"from": alice})

    yfi.approve(ve_yfi.address, amount * 10, {"from": alice})
    yfi.approve(ve_yfi.address, amount * 10, {"from": bob})

    chain.sleep((chain[-1].timestamp // WEEK + 1) * WEEK - chain[-1].timestamp)
    chain.mine()

    chain.sleep(H)

    ve_yfi.create_lock(amount, chain[-1].timestamp + 2 * WEEK, {"from": alice})
    ve_yfi.create_lock(amount, chain[-1].timestamp + WEEK, {"from": bob})

    next_ve = gov.deploy(NextVe, yfi)
    ve_yfi.set_next_ve_contract(next_ve)

    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.balanceOf(bob) == 0
    assert ve_yfi.totalSupply() == 0


def test_create_lock_for(
    web3, chain, accounts, yfi, ve_yfi, gov, panda, doggie, ve_yfi_rewards
):
    amount = 1000 * 10**18
    yfi.mint(gov, amount, {"from": gov})
    yfi.mint(gov, amount, {"from": panda})

    yfi.approve(ve_yfi.address, amount * 10, {"from": gov})
    yfi.approve(ve_yfi.address, amount * 10, {"from": panda})

    chain.sleep((chain[-1].timestamp // WEEK + 1) * WEEK - chain[-1].timestamp)
    chain.mine()

    chain.sleep(H)

    with brownie.reverts("dev: only admin"):
        ve_yfi.create_lock_for(
            doggie, amount, chain[-1].timestamp + 2 * WEEK, {"from": panda}
        )
    ve_yfi.create_lock_for(
        doggie, amount, chain[-1].timestamp + 2 * WEEK, {"from": gov}
    )

    with brownie.reverts("Withdraw old tokens first"):
        ve_yfi.create_lock_for(
            doggie, amount, chain[-1].timestamp + 2 * WEEK, {"from": gov}
        )


def test_commit_admin_only(ve_yfi, accounts):
    with brownie.reverts("dev: admin only"):
        ve_yfi.commit_transfer_ownership(accounts[1], {"from": accounts[1]})


def test_apply_admin_only(ve_yfi, accounts):
    with brownie.reverts("dev: admin only"):
        ve_yfi.apply_transfer_ownership({"from": accounts[1]})


def test_commit_transfer_ownership(ve_yfi, accounts):
    ve_yfi.commit_transfer_ownership(accounts[1], {"from": accounts[0]})

    assert ve_yfi.admin() == accounts[0]
    assert ve_yfi.future_admin() == accounts[1]


def test_apply_transfer_ownership(ve_yfi, accounts):
    ve_yfi.commit_transfer_ownership(accounts[1], {"from": accounts[0]})
    ve_yfi.apply_transfer_ownership({"from": accounts[0]})

    assert ve_yfi.admin() == accounts[1]


def test_apply_without_commit(ve_yfi, accounts):
    with brownie.reverts("dev: admin not set"):
        ve_yfi.apply_transfer_ownership({"from": accounts[0]})


def test_migrate_lock(
    chain, accounts, yfi, ve_yfi, gov, panda, doggie, ve_yfi_rewards, NextVe
):
    amount = 1000 * 10**18
    yfi.mint(panda, amount, {"from": panda})
    yfi.approve(ve_yfi.address, amount, {"from": panda})

    ve_yfi.create_lock(amount, chain[-1].timestamp + 2 * WEEK, {"from": panda})
    next_ve = gov.deploy(NextVe, yfi)
    ve_yfi.set_next_ve_contract(next_ve)
    ve_yfi.migrate({"from": panda})
    assert ve_yfi.balanceOf(panda) == 0

    assert yfi.balanceOf(next_ve) == amount
