import ape
import pytest
from ape import chain, project
from eth_utils import to_int


def test_gauge_yfi_distribution_full_rewards(
    yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)

    chain.mine(timestamp=chain.pending_timestamp + 3600)
    assert pytest.approx(gauge.earned(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    gauge.getReward(sender=whale)
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
    yfi.transfer(gov, whale_amount - 1, sender=whale)
    yfi.approve(ve_yfi, whale_amount - 1, sender=gov)
    ve_yfi.create_lock(
        whale_amount - 1, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=gov
    )
    yfi.approve(ve_yfi, 1, sender=whale)
    ve_yfi.create_lock(1, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale)

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)

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
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(panda, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=panda)
    gauge.deposit(sender=panda)

    vault.mint(panda, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=panda)
    gauge.deposit(sender=panda)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=panda)
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
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 2 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)

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
    tx = gauge.transferQueuedPenalty(sender=panda)
    # TODO: Should be `tx.RewardsAdded[0].currentRewards`
    # https://github.com/ApeWorX/ape/issues/571
    assert (
        yfi.balanceOf(ve_yfi_rewards)
        == ve_yfi_rewards.currentRewards()
        == to_int(hexstr=tx.logs[0]["data"])
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_gauge_get_reward_for(
    yfi, ve_yfi, whale, whale_amount, shark, create_vault, create_gauge, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getRewardFor(whale, False, sender=shark)

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
    assert gauge.totalSupply() == 0

    with ape.reverts("RewardPool : Cannot deposit 0"):
        gauge.depositFor(whale, 0, sender=shark)

    vault.mint(shark, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=shark)
    gauge.depositFor(whale, lp_amount, sender=shark)
    assert gauge.totalSupply() == 10**18
    assert gauge.balanceOf(whale) == 10**18

    with ape.reverts("RewardPool : Cannot deposit 0"):
        gauge.deposit(0, sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)
    assert gauge.totalSupply() == 2 * 10**18
    assert gauge.balanceOf(whale) == 2 * 10**18

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_withdraw(yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.withdraw(True, sender=whale)

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        7 * 24
    )
    assert gauge.queuedPenalty() == 0
    assert gauge.queuedRewards() == 0


def test_gauge_yfi_distribution_no_more_ve_yfi(
    yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov
):
    # we create a big lock compared to what whale will deposit so he doesn't have a boost.
    # User should also suffer penalty since he only locked for a year but after veYFI unlocks
    #  the boost and the penalty meachnisms are removed.
    yfi.transfer(gov, whale_amount - 1, sender=whale)
    yfi.approve(ve_yfi, whale_amount - 1, sender=gov)
    ve_yfi.create_lock(
        whale_amount - 1, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=gov
    )
    yfi.approve(ve_yfi, 1, sender=whale)
    ve_yfi.create_lock(1, chain.pending_timestamp + 3600 * 24 * 365, sender=whale)

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (7 * 24 * 3600)
    chain.pending_timestamp += 3600
    next_ve = gov.deploy(project.NextVe, yfi)
    ve_yfi.set_next_ve_contract(next_ve, sender=gov)

    gauge.getReward(sender=whale)

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
    gauge = create_gauge(vault)

    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)
    chain.pending_timestamp += 3600

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    chain.pending_timestamp += 3600
    tx = gauge.getReward(True, False, sender=whale)
    assert (
        ve_yfi.locked(whale)[0]
        # TODO: Should be `tx.RewardPaid[0].reward`
        # https://github.com/ApeWorX/ape/issues/571
        == whale_amount + to_int(hexstr=tx.logs[0]["data"][4 * 64 + 2 :])
    )
