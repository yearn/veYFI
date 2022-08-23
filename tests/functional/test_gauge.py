import ape
from ape import project, chain
import pytest

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def test_set_reward_manager(create_vault, create_gauge, panda, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    with ape.reverts("_rewardManager 0x0 address"):
        gauge.setRewardManager(ZERO_ADDRESS, sender=gov)
    with ape.reverts("!authorized"):
        gauge.setRewardManager(panda, sender=panda)

    gauge.setRewardManager(panda, sender=gov)
    assert gauge.rewardManager() == panda

    gauge.setRewardManager(gov, sender=panda)
    assert gauge.rewardManager() == gov


def test_set_gov(create_vault, create_gauge, panda, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    with ape.reverts("new owner is the zero address"):
        gauge.transferOwnership(ZERO_ADDRESS, sender=gov)
    with ape.reverts("caller is not the owner"):
        gauge.transferOwnership(panda, sender=panda)

    gauge.transferOwnership(panda, sender=gov)
    assert gauge.owner() == panda


def test_do_not_queue_zero_rewards(create_vault, create_gauge, panda):
    vault = create_vault()
    gauge = create_gauge(vault)
    with ape.reverts("==0"):
        gauge.queueNewRewards(0, sender=panda)


def test_sweep(create_vault, create_gauge, create_token, yfi, whale, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    yfo.mint(gauge, 10**18, sender=gov)
    with ape.reverts("caller is not the owner"):
        gauge.sweep(yfo, sender=whale)
    with ape.reverts("protected token"):
        gauge.sweep(yfi, sender=gov)
    with ape.reverts("protected token"):
        gauge.sweep(vault, sender=gov)
    gauge.sweep(yfo, sender=gov)
    assert yfo.balanceOf(gov) == 10**18


def test_add_extra_reward(
    create_vault, create_gauge, create_token, create_extra_reward, gov, panda
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")

    extra_reward = create_extra_reward(gauge, yfo)
    with ape.reverts("!authorized"):
        gauge.addExtraReward(extra_reward, sender=panda)
    with ape.reverts("!reward setting"):
        gauge.addExtraReward(ZERO_ADDRESS, sender=gov)

    gauge.addExtraReward(extra_reward, sender=gov)
    assert gauge.extraRewardsLength() == 1


def test_remove_extra_reward(
    create_vault, create_gauge, create_token, create_extra_reward, gov, panda
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    yfp = create_token("YFP")

    yfo_extra_reward = create_extra_reward(gauge, yfo)
    with ape.reverts("extra reward not found"):
        gauge.removeExtraReward(yfo_extra_reward, sender=gov)
    gauge.addExtraReward(yfo_extra_reward, sender=gov)

    yfp_extra_reward = create_extra_reward(gauge, yfp)
    gauge.addExtraReward(yfp_extra_reward, sender=gov)
    assert gauge.extraRewardsLength() == 2

    with ape.reverts("!authorized"):
        gauge.removeExtraReward(yfp_extra_reward, sender=panda)

    gauge.removeExtraReward(yfp_extra_reward, sender=gov)
    gauge.removeExtraReward(yfo_extra_reward, sender=gov)
    assert gauge.extraRewardsLength() == 0


def test_clear_extra_rewards(
    create_vault, create_gauge, create_token, create_extra_reward, gov
):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfo = create_token("YFO")
    yfp = create_token("YFP")

    yfo_extra_reward = create_extra_reward(gauge, yfo)
    gauge.addExtraReward(yfo_extra_reward, sender=gov)

    yfp_extra_reward = create_extra_reward(gauge, yfp)
    gauge.addExtraReward(yfp_extra_reward, sender=gov)
    assert gauge.extraRewardsLength() == 2

    gauge.clearExtraRewards(sender=gov)
    assert gauge.extraRewardsLength() == 0


def test_small_queued_rewards_duration_extension(create_vault, create_gauge, yfi, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfi_to_distribute = 10**20
    yfi.mint(gov, yfi_to_distribute * 2, sender=gov)
    yfi.approve(gauge, yfi_to_distribute * 2, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
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


def test_set_duration(create_vault, create_gauge, yfi, gov):
    vault = create_vault()
    gauge = create_gauge(vault)
    yfi_to_distribute = 10**20
    yfi.mint(gov, yfi_to_distribute * 2, sender=gov)
    yfi.approve(gauge, yfi_to_distribute * 2, sender=gov)
    gauge.queueNewRewards(yfi_to_distribute, sender=gov)

    finish = gauge.periodFinish()
    rate = gauge.rewardRate()
    chain.mine()
    time = chain.blocks.head.timestamp
    gauge.setDuration(28 * 3600 * 24, sender=gov)

    assert pytest.approx(rate / 2, rel=10e-3) == gauge.rewardRate()
    assert gauge.duration() == 28 * 3600 * 24
    assert gauge.periodFinish() != finish
    assert pytest.approx(gauge.periodFinish()) == time + 28 * 3600 * 24


def test_set_boosting_factor(
    create_vault, create_gauge, whale_amount, panda, yfi, ve_yfi, whale, gov
):
    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )

    yfi.mint(panda, whale_amount, sender=panda)
    yfi.approve(ve_yfi, whale_amount, sender=panda)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=panda
    )

    vault.mint(whale, lp_amount, sender=whale)

    vault.approve(gauge, lp_amount, sender=whale)

    gauge.deposit(sender=whale)

    with ape.reverts("caller is not the owner"):
        gauge.setBoostingFactor(200, sender=panda)

    with ape.reverts("value too low"):
        gauge.setBoostingFactor(5, sender=gov)

    with ape.reverts("value too high"):
        gauge.setBoostingFactor(1000, sender=gov)

    gauge.setBoostingFactor(200, sender=gov)

    assert gauge.nextBoostedBalanceOf(whale) > gauge.boostedBalanceOf(whale)
