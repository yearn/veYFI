import pytest
from ape import chain, project
import ape

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DAY = 86400
WEEK = 7 * DAY
MAXTIME = 126144000 // WEEK * WEEK


def test_extra_rewards_full_boost(
    yfi,
    ve_yfi,
    whale,
    whale_amount,
    create_vault,
    create_gauge,
    create_token,
    create_extra_reward,
    gov,
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(whale_amount, chain.pending_timestamp + MAXTIME, sender=whale)
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")

    extra_reward = create_extra_reward(gauge, yfo)
    gauge.addExtraReward(extra_reward, sender=gov)

    yfo.mint(gov, 10**18, sender=gov)
    yfo.approve(extra_reward, 10**18, sender=gov)
    extra_reward.queueNewRewards(10**18, sender=gov)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)
    chain.pending_timestamp += 3600
    chain.mine()
    extra_reward.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 14 / 24

    chain.pending_timestamp += 3600
    chain.mine()
    gauge.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 14 / 12


def test_extra_rewards_no_boost(
    yfi,
    ve_yfi,
    whale,
    whale_amount,
    create_vault,
    create_gauge,
    create_token,
    create_extra_reward,
    gov,
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(whale_amount, chain.pending_timestamp + MAXTIME, sender=whale)

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")

    extra_reward = create_extra_reward(gauge, yfo)
    gauge.addExtraReward(extra_reward, sender=gov)

    yfo.mint(gov, lp_amount, sender=gov)
    yfo.approve(extra_reward, lp_amount, sender=gov)
    assert extra_reward.rewardPerToken() == 0
    extra_reward.queueNewRewards(lp_amount, sender=gov)
    chain.pending_timestamp += 10

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)
    chain.pending_timestamp += 3600
    chain.mine()
    v = extra_reward.earned(whale)
    assert pytest.approx(extra_reward.earned(whale), rel=10e-4) == 10**18 / 14 / 24
    extra_reward.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 14 / 24

    chain.pending_timestamp += 3600
    chain.mine()
    gauge.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 14 / 12


def test_withdraw_from_gauge_claim_extra_rewards(
    create_vault, create_gauge, create_token, create_extra_reward, gov, whale
):
    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")

    extra_reward = create_extra_reward(gauge, yfo)
    gauge.addExtraReward(extra_reward, sender=gov)

    yfo.mint(gov, 10**18, sender=gov)
    yfo.approve(extra_reward, 10**18, sender=gov)
    extra_reward.queueNewRewards(10**18, sender=gov)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)
    chain.pending_timestamp += 3600
    chain.mine()
    extra_reward.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 14 / 24

    chain.pending_timestamp += 3600
    chain.mine()
    gauge.withdraw(True, sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 14 / 12


def test_small_queued_rewards_duration_extension(
    create_vault, create_gauge, create_token, create_extra_reward, gov
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")

    extra_reward = create_extra_reward(gauge, yfo)
    gauge.addExtraReward(extra_reward, sender=gov)

    yfo.mint(gov, 3 * 10**20, sender=gov)
    yfo.approve(extra_reward, 3 * 10**20, sender=gov)
    extra_reward.queueNewRewards(10**20, sender=gov)

    finish = extra_reward.periodFinish()
    # distribution started, do not extend the duration unless rewards are 120% of what has been distributed.
    chain.pending_timestamp += 24 * 3600
    # Should have distributed 1/14, adding 1% will not trigger an update.
    chain.mine()
    extra_reward.queueNewRewards(10**18, sender=gov)

    assert extra_reward.queuedRewards() == 10**18
    assert extra_reward.periodFinish() == finish
    chain.pending_timestamp += 10

    # If more than 120% of what has been distributed is queued -> make a new period
    extra_reward.queueNewRewards(int(10**20 / 14 * 1.2), sender=gov)
    assert finish != extra_reward.periodFinish()
    assert extra_reward.periodFinish() != finish


def test_set_gov(
    create_vault, create_gauge, panda, gov, create_token, create_extra_reward
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    extra_reward = create_extra_reward(gauge, yfo)

    with ape.reverts("new owner is the zero address"):
        extra_reward.transferOwnership(ZERO_ADDRESS, sender=gov)
    with ape.reverts("caller is not the owner"):
        extra_reward.transferOwnership(panda, sender=panda)

    extra_reward.transferOwnership(panda, sender=gov)
    assert extra_reward.owner() == panda


def test_sweep(
    create_vault, create_gauge, create_token, create_extra_reward, whale, gov
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    extra_reward = create_extra_reward(gauge, yfo)

    yfx = create_token("YFX")
    yfx.mint(extra_reward, 10**18, sender=gov)
    with ape.reverts("caller is not the owner"):
        extra_reward.sweep(yfo, sender=whale)
    with ape.reverts("protected token"):
        extra_reward.sweep(yfo, sender=gov)

    extra_reward.sweep(yfx, sender=gov)
    assert yfx.balanceOf(gov) == 10**18
