import ape
import pytest
from ape import chain

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def test_ve_yfi_distribution(yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards, gov):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)
    yfi.approve(ve_yfi_rewards, rewards, sender=gov)
    ve_yfi_rewards.queueNewRewards(rewards, sender=gov)
    assert ve_yfi_rewards.rewardRate() == int(rewards / 7 / 24 / 3600)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.getReward(sender=whale)
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards / 7 / 24
    chain.pending_timestamp += 3600 * 24 * 7
    chain.mine()
    assert pytest.approx(ve_yfi_rewards.earned(whale), rel=10e-3) == rewards
    ve_yfi_rewards.getReward(False, sender=whale)
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards


def test_ve_yfi_distribution_relock(
    yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)
    yfi.approve(ve_yfi_rewards, rewards, sender=gov)
    ve_yfi_rewards.queueNewRewards(rewards, sender=gov)
    assert ve_yfi_rewards.rewardRate() == int(rewards / 7 / 24 / 3600)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.getReward(True, sender=whale)
    assert pytest.approx(ve_yfi.locked(whale)[0]) == rewards / 7 / 24 + whale_amount
    chain.pending_timestamp += 3600 * 24 * 7
    ve_yfi_rewards.getReward(True, sender=whale)
    assert pytest.approx(ve_yfi.locked(whale)[0]) == rewards + whale_amount


def test_ve_yfi_get_rewards_for(
    yfi, ve_yfi, whale, fish, whale_amount, ve_yfi_rewards, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)
    yfi.approve(ve_yfi_rewards, rewards, sender=gov)
    ve_yfi_rewards.queueNewRewards(rewards, sender=gov)
    assert ve_yfi_rewards.rewardRate() == int(rewards / 7 / 24 / 3600)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.getRewardFor(whale, sender=fish)
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards / 7 / 24


def test_sweep(yfi, ve_yfi, ve_yfi_rewards, create_token, whale, whale_amount, gov):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    yfo = create_token("YFO")
    yfo.mint(ve_yfi_rewards, 10**18, sender=gov)
    with ape.reverts("Ownable: caller is not the owner"):
        ve_yfi_rewards.sweep(yfo, sender=whale)
    with ape.reverts("protected token"):
        ve_yfi_rewards.sweep(yfi, sender=gov)
    ve_yfi_rewards.sweep(yfo, sender=gov)
    assert yfo.balanceOf(gov) == 10**18


def test_set_gov(ve_yfi_rewards, panda, gov):
    with ape.reverts("Ownable: new owner is the zero address"):
        ve_yfi_rewards.transferOwnership(ZERO_ADDRESS, sender=gov)
    with ape.reverts("Ownable: caller is not the owner"):
        ve_yfi_rewards.transferOwnership(panda, sender=panda)

    ve_yfi_rewards.transferOwnership(panda, sender=gov)
    assert ve_yfi_rewards.owner() == panda


def test_reward_checkpoint(ve_yfi_rewards, ve_yfi, panda, gov):
    with ape.reverts("!authorized"):
        ve_yfi_rewards.rewardCheckpoint(panda, sender=panda)
    with ape.reverts("!authorized"):
        ve_yfi_rewards.rewardCheckpoint(panda, sender=gov)
    # TODO: `.address` is hack to support calling via `sender=ContractInstance`
    # ref: https://github.com/ApeWorX/ape/issues/606
    ve_yfi_rewards.rewardCheckpoint(panda, sender=ve_yfi.address)


def test_small_queued_rewards_duration_extension(ve_yfi_rewards, yfi, gov):

    yfi_to_distribute = 10**20
    yfi.mint(gov, yfi_to_distribute * 2, sender=gov)
    yfi.approve(ve_yfi_rewards, yfi_to_distribute * 2, sender=gov)

    ve_yfi_rewards.queueNewRewards(yfi_to_distribute, sender=gov)
    finish = ve_yfi_rewards.periodFinish()
    # distribution started, do not extend the duration unless rewards are 120% of what has been distributed.
    chain.pending_timestamp += 24 * 3600
    # Should have distributed 1/7, adding 1% will not trigger an update.
    ve_yfi_rewards.queueNewRewards(10**18, sender=gov)
    assert ve_yfi_rewards.queuedRewards() == 10**18
    assert ve_yfi_rewards.periodFinish() == finish
    chain.pending_timestamp += 10

    # If more than 120% of what has been distributed is queued -> make a new period
    ve_yfi_rewards.queueNewRewards(int(10**20 / 7 * 1.2), sender=gov)
    assert finish != ve_yfi_rewards.periodFinish()
    assert ve_yfi_rewards.periodFinish() != finish
