import ape
import pytest
from ape import chain, project
from eth_utils import to_int


def test_gauge_yfi_distribution_full_rewards(
    yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)

    chain.mine(timestamp=chain.pending_timestamp + 3600)
    assert pytest.approx(gauge.earned(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    gauge.getReward(sender=whale)
    assert gauge.rewardPerToken() > 0

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
    assert gauge.queuedRewards() == 0


def test_gauge_yfi_distribution_no_boost(
    yfi, ve_yfi, panda, create_vault, create_gauge, gov
):
    # we create a big lock compared to what panda will deposit so he doesn't have a boost.
    yfi.mint(gov, 10**18, sender=gov)
    yfi.approve(ve_yfi, 10**18, sender=gov)
    ve_yfi.modify_lock(
        10**18, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=gov
    )

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(panda, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=panda)
    gauge.deposit(sender=panda)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=panda)

    assert (
        pytest.approx(yfi.balanceOf(panda), rel=5 * 10e-4)
        == yfi_to_distribute / (14 * 24) * 0.1
    )

    assert (
        pytest.approx(gauge.queuedVeYfiRewards(), rel=10e-4)
        == yfi_to_distribute / (14 * 24) * 0.9
    )


def test_boost_lock(
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
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )

    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600

    yfi.mint(panda, whale_amount, sender=panda)
    yfi.approve(ve_yfi, whale_amount, sender=panda)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=panda
    )

    gauge.getReward(sender=whale)

    assert pytest.approx(yfi.balanceOf(whale), rel=10e-3) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
    assert (
        pytest.approx(gauge.boostedBalanceOf(whale))
        == gauge.nextBoostedBalanceOf(whale)
        == (0.1 * lp_amount)
        + (lp_amount * ve_yfi.balanceOf(whale) / ve_yfi.totalSupply() * 0.9)
    )


def test_gauge_get_reward_for(
    yfi, ve_yfi, whale, whale_amount, shark, create_vault, create_gauge, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    with ape.reverts("not allowed to claim"):
        gauge.getRewardFor(whale, False, True, sender=shark)

    gauge.setApprovals(shark, True, False, sender=whale)

    with ape.reverts("not allowed to lock"):
        gauge.getRewardFor(whale, True, True, sender=shark)

    gauge.getRewardFor(whale, False, True, sender=shark)

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
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
    ve_yfi.modify_lock(
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
        gauge.deposit(0, whale, sender=shark)

    vault.mint(shark, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=shark)

    gauge.deposit(lp_amount, whale, sender=shark)
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
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
    assert gauge.queuedRewards() == 0


def test_withdraw(yfi, ve_yfi, whale, whale_amount, create_vault, create_gauge, gov):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.withdraw(True, sender=whale)

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
    assert gauge.queuedRewards() == 0


def test_claim_and_lock_rewards(
    create_vault, create_gauge, whale_amount, yfi, ve_yfi, whale, gov
):
    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
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
        == whale_amount + next(tx.decode_logs(gauge.RewardPaid)).reward
    )


def test_kick(create_vault, create_gauge, whale_amount, panda, yfi, ve_yfi, whale, gov):
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
    vault.mint(panda, lp_amount, sender=panda)

    vault.approve(gauge, lp_amount, sender=whale)
    vault.approve(gauge, lp_amount, sender=panda)

    gauge.deposit(sender=panda)
    gauge.deposit(sender=whale)
    assert gauge.boostedBalanceOf(whale) == gauge.nextBoostedBalanceOf(whale)
    gauge.withdraw(int(lp_amount / 100), panda, panda, False, False, sender=panda)
    assert gauge.boostedBalanceOf(whale) != gauge.nextBoostedBalanceOf(whale)
    gauge.kick([whale], sender=panda)

    assert (
        gauge.nextBoostedBalanceOf(whale)
        == gauge.boostedBalanceOf(whale)
        != gauge.balanceOf(whale)
    )


def withdraw_for(
    yfi, ve_yfi, whale, panda, whale_amount, create_vault, create_gauge, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.approve(panda, lp_amount, sender=whale)

    gauge.withdraw(lp_amount, whale, panda, True, False, sender=panda)

    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
    assert gauge.queuedRewards() == 0


def transfer(yfi, ve_yfi, whale, panda, whale_amount, create_vault, create_gauge, gov):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    yfi_to_distribute = 10**16
    yfi.mint(gov, yfi_to_distribute, sender=gov)
    yfi.approve(gauge, yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.approve(panda, lp_amount, sender=whale)

    gauge.transferFrom(whale, panda, lp_amount, sender=panda)
    gauge.getReward(sender=whale)

    assert gauge.boostedBalance(whale) == 0
    assert pytest.approx(yfi.balanceOf(whale), rel=5 * 10e-4) == yfi_to_distribute / (
        14 * 24
    )
    assert gauge.queuedVeYfiRewards() == 0
    assert gauge.queuedRewards() == 0
