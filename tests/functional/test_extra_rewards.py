from pathlib import Path
import brownie

import pytest
from brownie import chain, Gauge, ExtraReward


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
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount, chain.time() + 4 * 3600 * 24 * 365, {"from": whale}
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")

    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])
    gauge.addExtraReward(extra_reward, {"from": gov})

    yfo.mint(gov, 10**18)
    yfo.approve(extra_reward, 10**18)
    extra_reward.queueNewRewards(10**18, {"from": gov})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})
    chain.sleep(3600)
    extra_reward.rewardCheckpoint(whale, {"from": gauge})
    assert pytest.approx(extra_reward.rewardPerToken(), rel=10e-4) == 10**18 / 7 / 24
    assert extra_reward.queuedRewards() == 0
    extra_reward.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24

    chain.sleep(3600)
    extra_reward.rewardCheckpoint(whale, {"from": gauge})
    assert (
        pytest.approx(extra_reward.rewardPerToken(), rel=10e-4) == 2 * 10**18 / 7 / 24
    )
    assert extra_reward.queuedRewards() == 0
    gauge.getReward({"from": whale})
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
    yfi.transfer(gov, whale_amount - 1, {"from": whale})
    yfi.approve(ve_yfi, whale_amount - 1, {"from": gov})
    ve_yfi.create_lock(
        whale_amount - 1, chain.time() + 4 * 3600 * 24 * 365, {"from": gov}
    )
    yfi.approve(ve_yfi, 1, {"from": whale})
    ve_yfi.create_lock(1, chain.time() + 4 * 3600 * 24 * 365, {"from": whale})
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")

    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])
    gauge.addExtraReward(extra_reward, {"from": gov})

    yfo.mint(gov, 10**18)
    yfo.approve(extra_reward, 10**18)
    extra_reward.queueNewRewards(10**18, {"from": gov})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})
    chain.sleep(3600)
    extra_reward.rewardCheckpoint(whale, {"from": gauge})
    assert pytest.approx(extra_reward.rewardPerToken(), rel=10e-4) == 10**18 / 7 / 24
    # boost ~= .4 as whale lock is small compared to gov lock
    assert pytest.approx(extra_reward.queuedRewards(), rel=10e-4) == 0.6 * (
        10**18 / 7 / 24
    )
    extra_reward.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24 * 0.4

    chain.sleep(3600)
    extra_reward.rewardCheckpoint(whale, {"from": gauge})
    assert (
        pytest.approx(extra_reward.rewardPerToken(), rel=10e-4) == 2 * 10**18 / 7 / 24
    )
    assert pytest.approx(extra_reward.queuedRewards(), rel=10e-4) == 1.2 * (
        10**18 / 7 / 24
    )
    gauge.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 12 * 0.4


def test_donate_and_multiple_queue_rewards(
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
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount, chain.time() + 4 * 3600 * 24 * 365, {"from": whale}
    )
    assert yfi.balanceOf(whale) == 0

    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")

    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])
    gauge.addExtraReward(extra_reward, {"from": gov})

    yfo.mint(whale, 10**18)
    yfo.approve(extra_reward, 10**18, {"from": whale})
    with brownie.reverts("==0"):
        extra_reward.donate(0, {"from": whale})
    extra_reward.donate(10**18, {"from": whale})
    assert extra_reward.queuedRewards() == 10**18

    yfo.mint(gov, 2 * 10**18)
    yfo.approve(extra_reward, 2 * 10**18, {"from": gov})
    with brownie.reverts("==0"):
        extra_reward.queueNewRewards(0, {"from": gov})
    extra_reward.queueNewRewards(10**18, {"from": gov})
    assert (
        pytest.approx(extra_reward.rewardRate(), rel=10e-4)
        == 2 * 10**18 / 3600 / 7 / 24
    )

    chain.sleep(3600 * 24)
    extra_reward.queueNewRewards(10**18, {"from": gov})
    # 6/7 of prior reward + current reward
    assert (
        pytest.approx(extra_reward.rewardRate(), rel=10e-4)
        == (2 * 6 / 7 + 1) * 10**18 / 3600 / 7 / 24
    )
    assert extra_reward.queuedRewards() == 0
