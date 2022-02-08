from pathlib import Path

import pytest
from brownie import chain


def test_ve_yfi_distribution(yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards, gov):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    rewards = 10 ** 18
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
    rewards = 10 ** 18
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
