import brownie
import pytest
from brownie import chain


def test_ve_yfi_distribution(yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards, gov):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    rewards = 10**18
    yfi.mint(gov, rewards)
    yfi.approve(ve_yfi_rewards, rewards)
    ve_yfi_rewards.queueNewRewards(rewards, {"from": gov})
    assert ve_yfi_rewards.rewardRate() == rewards / 7 / 24 / 3600
    chain.sleep(3600)
    ve_yfi_rewards.getReward(False, {"from": whale})
    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == rewards / 7 / 24
    chain.sleep(3600 * 24 * 7)
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


def test_sweep(yfi, ve_yfi, ve_yfi_rewards, create_token, whale, whale_amount, gov):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    yfo = create_token("YFO")
    yfo.mint(ve_yfi_rewards, 10**18)
    with brownie.reverts("!authorized"):
        ve_yfi_rewards.sweep(yfo, {"from": whale})
    with brownie.reverts("protected token"):
        ve_yfi_rewards.sweep(yfi, {"from": gov})
    ve_yfi_rewards.sweep(yfo, {"from": gov})
    assert yfo.balanceOf(gov) == 10**18
