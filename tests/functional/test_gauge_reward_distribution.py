import brownie
import pytest
from brownie import chain, Gauge, ExtraReward


def test_gauge_yfi_distribution_full_rewards(
    yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov
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

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)

    chain.sleep(3600)
    chain.mine()
    assert pytest.approx(gauge.earned(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    gauge.getReward({"from": whale})
    assert gauge.rewardPerToken() > 0

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_gauge_yfi_distribution_no_boost(
    yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov
):
    # we create a big lock compared to what whale will deposit so he doesn't have a boost.
    yfi.transfer(gov, whale_amount - 1, {"from": whale})
    yfi.approve(ve_yfi, whale_amount - 1, {"from": gov})
    ve_yfi.create_lock(
        whale_amount - 1, chain.time() + 4 * 3600 * 24 * 365, {"from": gov}
    )
    yfi.approve(ve_yfi, 1, {"from": whale})
    ve_yfi.create_lock(1, chain.time() + 4 * 3600 * 24 * 365, {"from": whale})

    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    gauge.getReward({"from": whale})

    assert (
        pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4)
        == yfi_to_distribute / (7 * 24) * 0.4
    )
    assert gauge.queuedPenalty() == 0
    assert (
        pytest.approx(gauge.queuedRewards(), rel=10e-4)
        == yfi_to_distribute / (7 * 24) * 0.6
    )


def test_gauge_yfi_distribution_no_lock_no_rewards(
    yfi, ve_yfi, whale, panda, whale_amount, create_vault, create_gauge, gov
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount, chain.time() + 4 * 3600 * 24 * 365, {"from": whale}
    )
    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    vault.mint(panda, lp_amount)
    vault.approve(gauge, lp_amount, {"from": panda})
    gauge.deposit({"from": panda})

    vault.mint(panda, lp_amount)
    vault.approve(gauge, lp_amount, {"from": panda})
    gauge.deposit({"from": panda})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    gauge.getReward({"from": panda})
    assert gauge.lockingRatio(panda) == 0

    assert yfi.balanceOf(panda) == 0

    assert (
        pytest.approx(gauge.queuedPenalty(), rel=10e-4)
        == yfi_to_distribute / (7 * 24) * 0.4
    )
    assert (
        pytest.approx(gauge.queuedRewards(), rel=10e-4)
        == yfi_to_distribute / (7 * 24) * 0.6
    )


def test_gauge_yfi_distribution_max_boost_only_two_years_lock(
    yfi,
    ve_yfi,
    whale,
    ve_yfi_rewards,
    whale_amount,
    create_vault,
    create_gauge,
    panda,
    gov,
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount, chain.time() + 2 * 3600 * 24 * 365, {"from": whale}
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    gauge.getReward({"from": whale})

    assert pytest.approx(gauge.lockingRatio(whale), rel=10e-2) == 500_000

    assert (
        pytest.approx(yfi.balanceOf(whale), rel=10e-3)
        == yfi_to_distribute / (7 * 24) / 2
    )
    assert (
        pytest.approx(gauge.queuedPenalty(), rel=10e-3)
        == yfi_to_distribute / (7 * 24) / 2
    )
    assert yfi.balanceOf(ve_yfi_rewards) == 0
    tx = gauge.transferQueuedPenalty({"from": panda})
    assert yfi.balanceOf(ve_yfi_rewards) == tx.events["RewardsAdded"]["currentRewards"]
    assert gauge.queuedPenalty() == 0

    assert (
        tx.events["RewardsAdded"]["currentRewards"] == ve_yfi_rewards.currentRewards()
    )
    assert gauge.queuedRewards() == 0


def test_gauge_get_reward_for(
    yfi, ve_yfi, whale, whale_amount, shark, create_vault, create_gauge, gov
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

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    gauge.getRewardFor(whale, False, {"from": shark})

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_deposit_for(
    yfi,
    ve_yfi,
    whale,
    shark,
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
    assert gauge.totalSupply() == 0

    with brownie.reverts("RewardPool : Cannot deposit 0"):
        gauge.depositFor(whale, 0, {"from": shark})

    vault.mint(shark, lp_amount)
    vault.approve(gauge, lp_amount, {"from": shark})
    gauge.depositFor(whale, lp_amount, {"from": shark})
    assert gauge.totalSupply() == 10**18
    assert gauge.balanceOf(whale) == 10**18

    with brownie.reverts("RewardPool : Cannot deposit 0"):
        gauge.deposit(0, {"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})
    assert gauge.totalSupply() == 2 * 10**18
    assert gauge.balanceOf(whale) == 2 * 10**18

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    gauge.getReward({"from": whale})

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_withdraw(yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount, chain.time() + 4 * 3600 * 24 * 365, {"from": whale}
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    gauge.withdraw(True, {"from": whale})

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_gauge_yfi_distribution_no_more_ve_yfi(
    yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov, NextVe
):
    # we create a big lock compared to what whale will deposit so he doesn't have a boost.
    # User should also suffer penalty since he only locked for a year but after veYFI unlocks
    #  the boost and the penalty meachnisms are removed.
    yfi.transfer(gov, whale_amount - 1, {"from": whale})
    yfi.approve(ve_yfi, whale_amount - 1, {"from": gov})
    ve_yfi.create_lock(
        whale_amount - 1, chain.time() + 4 * 3600 * 24 * 365, {"from": gov}
    )
    yfi.approve(ve_yfi, 1, {"from": whale})
    ve_yfi.create_lock(1, chain.time() + 3600 * 24 * 365, {"from": whale})

    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.sleep(3600)
    next_ve = gov.deploy(NextVe, yfi)
    ve_yfi.set_next_ve_contract(next_ve)

    gauge.getReward({"from": whale})

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_claim_and_lock_rewards(
    create_vault, create_gauge, whale_amount, yfi, ve_yfi, whale, gov
):
    lp_amount = 10**18
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount, chain.time() + 4 * 3600 * 24 * 365, {"from": whale}
    )

    vault.mint(whale, lp_amount)
    vault.approve(gauge, lp_amount, {"from": whale})
    gauge.deposit({"from": whale})
    chain.sleep(3600)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute)
    yfi.approve(gauge, yfi_to_distribute, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    chain.sleep(3600)
    tx = gauge.getReward(True, False, {"from": whale})
    assert (
        ve_yfi.locked(whale).dict()["amount"]
        == whale_amount + tx.events["RewardPaid"]["reward"]
    )
