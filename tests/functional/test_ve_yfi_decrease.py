import pytest
from ape import chain

H = 3600
DAY = 86400
WEEK = 7 * DAY
MAXTIME = 4 * 365 * 86400 // WEEK * WEEK
TOL = 120 / WEEK
AMOUNT = 10**18
POWER = AMOUNT // MAXTIME * MAXTIME


@pytest.fixture()
def bob(accounts, yfi, ve_yfi):
    bob = accounts[1]
    yfi.mint(bob, AMOUNT * 20, sender=bob)
    yfi.approve(ve_yfi.address, AMOUNT * 20, sender=bob)
    now = chain.blocks.head.timestamp
    unlock_time = now + MAXTIME * 3
    ve_yfi.modify_lock(AMOUNT, unlock_time, sender=bob)
    yield bob


@pytest.fixture()
def alice(accounts, yfi, ve_yfi):
    alice = accounts[0]
    yfi.mint(alice, AMOUNT * 20, sender=alice)
    yfi.approve(ve_yfi.address, AMOUNT * 20, sender=alice)

    yield alice


def test_new_lock_less_than_max(alice, bob, ve_yfi):
    assert ve_yfi.totalSupply() == POWER
    now = chain.blocks.head.timestamp
    unlock_time = now + MAXTIME // 20
    ve_yfi.modify_lock(AMOUNT, unlock_time, sender=alice)
    assert pytest.approx(ve_yfi.balanceOf(alice), rel=10e-2) == (AMOUNT / 20)

    point = ve_yfi.point_history(alice, 1)
    lock = ve_yfi.locked(alice)
    assert point.slope == AMOUNT // MAXTIME
    assert lock.end == unlock_time // WEEK * WEEK

    chain.pending_timestamp += MAXTIME // 20
    chain.mine()

    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.totalSupply() == POWER
    assert ve_yfi.balanceOf(bob) == POWER


def test_new_lock_over_max(alice, bob, ve_yfi):
    assert ve_yfi.totalSupply() == POWER
    now = chain.blocks.head.timestamp
    unlock_time = now + MAXTIME + 4 * WEEK
    ve_yfi.modify_lock(AMOUNT, unlock_time, sender=alice)
    assert ve_yfi.balanceOf(alice) == POWER

    point = ve_yfi.point_history(alice, 1)
    lock = ve_yfi.locked(alice)
    assert point.slope == 0
    assert lock.end == unlock_time // WEEK * WEEK
    slop_change_time = lock.end - MAXTIME
    assert ve_yfi.slope_changes(alice, slop_change_time) == AMOUNT // MAXTIME
    assert ve_yfi.slope_changes(alice, lock.end) == -(AMOUNT // MAXTIME)

    chain.pending_timestamp += MAXTIME + 4 * WEEK
    chain.mine()
    assert ve_yfi.balanceOf(alice) == 0
    assert ve_yfi.totalSupply() == POWER
    assert ve_yfi.balanceOf(bob) == POWER


def test_change_lock_from_above_max_to_max(alice, bob, ve_yfi):
    assert ve_yfi.totalSupply() == POWER
    now = chain.blocks.head.timestamp
    unlock_time = now + MAXTIME + 4 * WEEK
    ve_yfi.modify_lock(AMOUNT, unlock_time, sender=alice)
    point = ve_yfi.point_history(alice, 1)
    lock = ve_yfi.locked(alice)
    assert point.slope == 0
    assert lock.end == unlock_time // WEEK * WEEK
    slop_change_time = lock.end - MAXTIME
    assert ve_yfi.slope_changes(alice, slop_change_time) == AMOUNT // MAXTIME
    assert ve_yfi.slope_changes(alice, lock.end) == -(AMOUNT // MAXTIME)

    ve_yfi.modify_lock(0, now + MAXTIME + WEEK, sender=alice)

    new_point = ve_yfi.point_history(alice, 2)
    new_lock = ve_yfi.locked(alice)
    assert new_point.slope == 0
    assert new_lock.end == (now + MAXTIME + WEEK) // WEEK * WEEK
    new_slop_change_time = new_lock.end - MAXTIME
    assert ve_yfi.slope_changes(alice, new_slop_change_time) == AMOUNT // MAXTIME
    assert ve_yfi.slope_changes(alice, new_lock.end) == -(AMOUNT // MAXTIME)
    assert ve_yfi.slope_changes(alice, slop_change_time) == 0
    assert ve_yfi.slope_changes(alice, lock.end) == 0


def test_checkpoint_after_kink_starts(alice, bob, ve_yfi):
    assert ve_yfi.totalSupply() == POWER
    now = chain.blocks.head.timestamp
    unlock_time = now + MAXTIME + 4 * WEEK
    ve_yfi.modify_lock(AMOUNT, unlock_time, sender=alice)
    point = ve_yfi.point_history(alice, 1)
    lock = ve_yfi.locked(alice)
    assert point.slope == 0
    assert lock.end == unlock_time // WEEK * WEEK
    slop_change_time = lock.end - MAXTIME
    assert ve_yfi.slope_changes(alice, slop_change_time) == AMOUNT // MAXTIME
    assert ve_yfi.slope_changes(alice, lock.end) == -(AMOUNT // MAXTIME)

    chain.pending_timestamp += 5 * WEEK
    chain.mine()
    assert ve_yfi.balanceOf(alice) < POWER
    ve_yfi.modify_lock(10**6, 0, sender=alice)  # trigger checkpoint.
    new_point = ve_yfi.point_history(alice, 2)
    assert new_point.slope == (AMOUNT + 10**6) // MAXTIME
    assert (
        ve_yfi.slope_changes(alice, slop_change_time) == AMOUNT // MAXTIME
    )  # no change in old slope
    assert ve_yfi.slope_changes(alice, lock.end) == -(AMOUNT // MAXTIME)
