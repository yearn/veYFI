import pytest
from ape import chain, project
import ape

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


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
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
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
    extra_reward.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24

    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 12


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
    # we create a big lock compared to what whale will deposit so he doesn't have a boost.
    yfi.transfer(gov, whale_amount - 1, sender=whale)
    yfi.approve(ve_yfi, whale_amount - 1, sender=gov)
    ve_yfi.create_lock(
        whale_amount - 1, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=gov
    )
    yfi.approve(ve_yfi, 1, sender=whale)
    ve_yfi.create_lock(1, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale)
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")

    extra_reward = create_extra_reward(gauge, yfo)
    gauge.addExtraReward(extra_reward, sender=gov)

    yfo.mint(gov, 10**18, sender=gov)
    yfo.approve(extra_reward, 10**18, sender=gov)
    extra_reward.rewardPerToken() == 0
    extra_reward.queueNewRewards(10**18, sender=gov)
    chain.pending_timestamp += 10
    extra_reward.rewardPerToken() != 0

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)
    chain.pending_timestamp += 3600
    chain.mine()
    assert (
        pytest.approx(extra_reward.earned(whale), rel=10e-4) == 10**18 / 7 / 24 * 0.4
    )
    extra_reward.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24 * 0.4

    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 12 * 0.4


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
    extra_reward.getReward(sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24

    chain.pending_timestamp += 3600
    gauge.withdraw(True, sender=whale)
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 12


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
    # Should have distributed 1/7, adding 1% will not trigger an update.

    extra_reward.queueNewRewards(10**18, sender=gov)

    assert extra_reward.queuedRewards() == 10**18
    assert extra_reward.periodFinish() == finish
    chain.pending_timestamp += 10

    # If more than 120% of what has been distributed is queued -> make a new period
    extra_reward.queueNewRewards(int(10**20 / 7 * 1.2), sender=gov)
    assert finish != extra_reward.periodFinish()
    assert extra_reward.periodFinish() != finish


def test_set_gov(
    create_vault, create_gauge, panda, gov, create_token, create_extra_reward
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    extra_reward = create_extra_reward(gauge, yfo)

    with ape.reverts("Ownable: new owner is the zero address"):
        extra_reward.transferOwnership(ZERO_ADDRESS, sender=gov)
    with ape.reverts("Ownable: caller is not the owner"):
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
    with ape.reverts("Ownable: caller is not the owner"):
        extra_reward.sweep(yfo, sender=whale)
    with ape.reverts("protected token"):
        extra_reward.sweep(yfo, sender=gov)

    extra_reward.sweep(yfx, sender=gov)
    assert yfx.balanceOf(gov) == 10**18
