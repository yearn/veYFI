import pytest
from brownie import chain, Gauge, ExtraReward, ZERO_ADDRESS
import brownie


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
    extra_reward.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24

    chain.sleep(3600)
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
    extra_reward.rewardPerToken() == 0
    extra_reward.queueNewRewards(10**18, {"from": gov})
    chain.sleep(10)
    extra_reward.rewardPerToken() != 0

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})
    chain.sleep(3600)
    chain.mine()
    assert (
        pytest.approx(extra_reward.earned(whale), rel=10e-4) == 10**18 / 7 / 24 * 0.4
    )
    extra_reward.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24 * 0.4

    chain.sleep(3600)
    gauge.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 12 * 0.4


def test_withdraw_from_gauge_claim_extra_rewards(
    create_vault, create_gauge, create_token, create_extra_reward, gov, whale
):
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
    extra_reward.getReward({"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 24

    chain.sleep(3600)
    gauge.withdraw(True, {"from": whale})
    assert pytest.approx(yfo.balanceOf(whale), rel=10e-4) == 10**18 / 7 / 12


def test_small_queued_rewards_duration_extension(
    create_vault, create_gauge, create_token, create_extra_reward, gov
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    yfo = create_token("YFO")

    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])
    gauge.addExtraReward(extra_reward, {"from": gov})

    yfo.mint(gov, 3 * 10**20)
    yfo.approve(extra_reward, 3 * 10**20)
    extra_reward.queueNewRewards(10**20, {"from": gov})

    finish = extra_reward.periodFinish()
    # distribution started, do not extend the duration unless rewards are 120% of what has been distributed.
    chain.sleep(24 * 3600)
    # Should have distributed 1/7, adding 1% will not trigger an update.

    extra_reward.queueNewRewards(10**18, {"from": gov})

    assert extra_reward.queuedRewards() == 10**18
    assert extra_reward.periodFinish() == finish
    chain.sleep(10)

    # If more than 120% of what has been distributed is queued -> make a new period
    extra_reward.queueNewRewards(10**20 / 7 * 1.2, {"from": gov})
    assert finish != extra_reward.periodFinish()
    assert extra_reward.periodFinish() != finish


def test_set_gov(
    create_vault, create_gauge, panda, gov, create_token, create_extra_reward
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")
    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])

    with brownie.reverts("Ownable: new owner is the zero address"):
        extra_reward.transferOwnership(ZERO_ADDRESS, {"from": gov})
    with brownie.reverts("Ownable: caller is not the owner"):
        extra_reward.transferOwnership(panda, {"from": panda})

    extra_reward.transferOwnership(panda, {"from": gov})
    assert extra_reward.owner() == panda


def test_sweep(
    create_vault, create_gauge, create_token, create_extra_reward, whale, gov
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")
    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])

    yfx = create_token("YFX")
    yfx.mint(extra_reward, 10**18)
    with brownie.reverts("Ownable: caller is not the owner"):
        extra_reward.sweep(yfo, {"from": whale})
    with brownie.reverts("protected token"):
        extra_reward.sweep(yfo, {"from": gov})

    extra_reward.sweep(yfx, {"from": gov})
    assert yfx.balanceOf(gov) == 10**18
