import ape
from ape import project, chain
import pytest

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

DAY = 86400
WEEK = 7 * DAY


@pytest.fixture(autouse=True)
def setup_time(chain):
    chain.pending_timestamp += WEEK - (
        chain.pending_timestamp - (chain.pending_timestamp // WEEK * WEEK)
    )
    chain.mine()


def test_set_gov(create_vault, create_gauge, panda, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    with ape.reverts("Ownable: new owner is the zero address"):
        gauge.transferOwnership(ZERO_ADDRESS, sender=gov)
    with ape.reverts("Ownable: caller is not the owner"):
        gauge.transferOwnership(panda, sender=panda)

    gauge.transferOwnership(panda, sender=gov)
    assert gauge.owner() == panda


def test_do_not_queue_zero_rewards(create_vault, create_gauge, panda):
    vault = create_vault()
    gauge = create_gauge(vault)
    with ape.reverts("==0"):
        gauge.queueNewRewards(0, sender=panda)


def test_sweep(create_vault, create_gauge, create_token, d_yfi, whale, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    yfo.mint(gauge, 10**18, sender=gov)
    with ape.reverts("Ownable: caller is not the owner"):
        gauge.sweep(yfo, sender=whale)
    with ape.reverts("protected token"):
        gauge.sweep(d_yfi, sender=gov)
    with ape.reverts("protected token"):
        gauge.sweep(vault, sender=gov)
    gauge.sweep(yfo, sender=gov)
    assert yfo.balanceOf(gov) == 10**18


def test_small_queued_rewards_duration_extension(
    create_vault, create_gauge, d_yfi, gov
):
    vault = create_vault()
    gauge = create_gauge(vault)
    d_yfi_to_distribute = 10**20
    d_yfi.mint(gov, d_yfi_to_distribute * 2, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute * 2, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    finish = gauge.periodFinish()
    # distribution started, do not extend the duration unless rewards are 120% of what has been distributed.
    chain.pending_timestamp += 24 * 3600
    # Should have distributed 1/7, adding 1% will not trigger an update.
    gauge.queueNewRewards(10**18, sender=gov)
    assert gauge.queuedRewards() == 10**18
    assert gauge.periodFinish() == finish
    chain.pending_timestamp += 10

    # If more than 120% of what has been distributed is queued -> make a new period
    gauge.queueNewRewards(int(10**20 / 7 * 1.2), sender=gov)
    assert finish != gauge.periodFinish()
    assert gauge.periodFinish() != finish


def test_set_duration(create_vault, create_gauge, d_yfi, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    d_yfi_to_distribute = 10**20
    d_yfi.mint(gov, d_yfi_to_distribute * 2, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute * 2, sender=gov)
    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)

    finish = gauge.periodFinish()
    rate = gauge.rewardRate()
    time = chain.blocks.head.timestamp
    gauge.setDuration(28 * 3600 * 24, sender=gov)

    assert pytest.approx(rate / 2, rel=10e-3) == gauge.rewardRate()
    assert gauge.duration() == 28 * 3600 * 24
    assert gauge.periodFinish() != finish
    assert pytest.approx(gauge.periodFinish()) == time + 28 * 3600 * 24
