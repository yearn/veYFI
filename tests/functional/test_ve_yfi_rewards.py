import brownie
import pytest
from brownie import chain, ZERO_ADDRESS


def test_ve_yfi_distribution(yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards, gov):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    rewards = 10**18
    yfi.mint(gov, rewards)
    yfi.approve(ve_yfi_rewards, rewards)
    ve_yfi_rewards.queueNewRewards(rewards, {"from": gov})
    assert ve_yfi_rewards.rewardRate() == rewards / 7 / 24 / 3600
    chain.sleep(3600)
    ve_yfi_rewards.getReward({"from": whale})
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards / 7 / 24
    chain.sleep(3600 * 24 * 7)
    chain.mine()
    assert pytest.approx(ve_yfi_rewards.earned(whale), rel=10e-3) == rewards
    ve_yfi_rewards.getReward(False, {"from": whale})
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards


def test_ve_yfi_distribution_relock(
    yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards, gov
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    rewards = 10**18
    yfi.mint(gov, rewards)
    yfi.approve(ve_yfi_rewards, rewards)
    ve_yfi_rewards.queueNewRewards(rewards, {"from": gov})
    assert ve_yfi_rewards.rewardRate() == rewards / 7 / 24 / 3600
    chain.sleep(3600)
    ve_yfi_rewards.getReward(True, {"from": whale})
    assert pytest.approx(ve_yfi.locked(whale)[0]) == rewards / 7 / 24 + whale_amount
    chain.sleep(3600 * 24 * 7)
    ve_yfi_rewards.getReward(True, {"from": whale})
    assert pytest.approx(ve_yfi.locked(whale)[0]) == rewards + whale_amount


def test_ve_yfi_get_rewards_for(
    yfi, ve_yfi, whale, fish, whale_amount, ve_yfi_rewards, gov
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    rewards = 10**18
    yfi.mint(gov, rewards)
    yfi.approve(ve_yfi_rewards, rewards)
    ve_yfi_rewards.queueNewRewards(rewards, {"from": gov})
    assert ve_yfi_rewards.rewardRate() == rewards / 7 / 24 / 3600
    chain.sleep(3600)
    ve_yfi_rewards.getRewardFor(whale, {"from": fish})
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards / 7 / 24


def test_sweep(yfi, ve_yfi, ve_yfi_rewards, create_token, whale, whale_amount, gov):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    yfo = create_token("YFO")
    yfo.mint(ve_yfi_rewards, 10**18)
    with brownie.reverts("Ownable: caller is not the owner"):
        ve_yfi_rewards.sweep(yfo, {"from": whale})
    with brownie.reverts("protected token"):
        ve_yfi_rewards.sweep(yfi, {"from": gov})
    ve_yfi_rewards.sweep(yfo, {"from": gov})
    assert yfo.balanceOf(gov) == 10**18


def test_set_gov(ve_yfi_rewards, panda, gov):
    with brownie.reverts("Ownable: new owner is the zero address"):
        ve_yfi_rewards.transferOwnership(ZERO_ADDRESS, {"from": gov})
    with brownie.reverts("Ownable: caller is not the owner"):
        ve_yfi_rewards.transferOwnership(panda, {"from": panda})

    ve_yfi_rewards.transferOwnership(panda, {"from": gov})
    assert ve_yfi_rewards.owner() == panda


def test_reward_checkpoint(ve_yfi_rewards, ve_yfi, panda, gov):
    with brownie.reverts():
        ve_yfi_rewards.rewardCheckpoint(panda, {"from": panda})
    ve_yfi_rewards.rewardCheckpoint(panda, {"from": ve_yfi})


def test_small_queued_rewards_duration_extension(ve_yfi_rewards, yfi, gov):

    yfi_to_distribute = 10**20
    yfi.mint(gov, yfi_to_distribute * 2)
    yfi.approve(ve_yfi_rewards, yfi_to_distribute * 2, {"from": gov})

    ve_yfi_rewards.queueNewRewards(yfi_to_distribute, {"from": gov})
    finish = ve_yfi_rewards.periodFinish()
    # distribution started, do not extend the duration unless rewards are 120% of what has been distributed.
    chain.sleep(24 * 3600)
    # Should have distributed 1/7, adding 1% will not trigger an update.
    ve_yfi_rewards.queueNewRewards(10**18, {"from": gov})
    assert ve_yfi_rewards.queuedRewards() == 10**18
    assert ve_yfi_rewards.periodFinish() == finish
    chain.sleep(10)

    # If more than 120% of what has been distributed is queued -> make a new period
    ve_yfi_rewards.queueNewRewards(10**20 / 7 * 1.2, {"from": gov})
    assert finish != ve_yfi_rewards.periodFinish()
    assert ve_yfi_rewards.periodFinish() != finish
