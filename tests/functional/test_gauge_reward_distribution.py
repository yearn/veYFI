import ape
import pytest
from ape import chain, project
from eth_utils import to_int

DAY = 86400
WEEK = 7 * DAY


@pytest.fixture(autouse=True)
def setup_time(chain):
    chain.pending_timestamp += WEEK - (
        chain.pending_timestamp - (chain.pending_timestamp // WEEK * WEEK)
    )
    chain.mine()


def test_gauge_yfi_distribution_full_rewards(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    create_vault,
    create_gauge,
    gov,
    ve_yfi_d_yfi_pool,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert d_yfi.balanceOf(whale) == 0
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)

    vault.mint(whale, lp_amount, sender=gov)
    vault.approve(gauge, lp_amount, sender=whale)
    gauge.deposit(sender=whale)

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)

    chain.mine(timestamp=chain.pending_timestamp + 3600)
    assert pytest.approx(gauge.earned(whale), rel=5 * 10e-4) == d_yfi_to_distribute / (
        14 * 24
    )
    gauge.getReward(sender=whale)
    assert gauge.rewardPerToken() > 0

    assert pytest.approx(
        d_yfi.balanceOf(whale), rel=5 * 10e-4
    ) == d_yfi_to_distribute / (14 * 24)
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert gauge.queuedRewards() == 0


def test_gauge_yfi_distribution_no_boost(
    yfi, d_yfi, ve_yfi, panda, create_vault, create_gauge, gov, ve_yfi_d_yfi_pool
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=panda)

    assert (
        pytest.approx(d_yfi.balanceOf(panda), rel=5 * 10e-4)
        == d_yfi_to_distribute / (14 * 24) * 0.1
    )

    assert (
        pytest.approx(d_yfi.balanceOf(ve_yfi_d_yfi_pool), rel=10e-4)
        == d_yfi_to_distribute / (14 * 24) * 0.9
    )


def test_boost_lock(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    create_vault,
    create_gauge,
    panda,
    gov,
    ve_yfi_d_yfi_pool,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600

    yfi.mint(panda, whale_amount, sender=panda)
    yfi.approve(ve_yfi, whale_amount, sender=panda)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=panda
    )

    gauge.getReward(sender=whale)

    assert pytest.approx(d_yfi.balanceOf(whale), rel=10e-3) == d_yfi_to_distribute / (
        14 * 24
    )
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert (
        pytest.approx(gauge.boostedBalanceOf(whale))
        == gauge.nextBoostedBalanceOf(whale)
        == (0.1 * lp_amount)
        + (lp_amount * ve_yfi.balanceOf(whale) / ve_yfi.totalSupply() * 0.9)
    )


def test_gauge_get_reward_for(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    shark,
    create_vault,
    create_gauge,
    gov,
    ve_yfi_d_yfi_pool,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(whale, sender=shark)

    assert pytest.approx(
        d_yfi.balanceOf(whale), rel=5 * 10e-4
    ) == d_yfi_to_distribute / (14 * 24)
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert gauge.queuedRewards() == 0


def test_deposit_for(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    shark,
    create_vault,
    create_gauge,
    ve_yfi_d_yfi_pool,
    gov,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 4 * 3600 * 24 * 365, sender=whale
    )
    assert yfi.balanceOf(whale) == 0

    lp_amount = 10**18
    vault = create_vault()
    gauge = create_gauge(vault)
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.getReward(sender=whale)

    assert pytest.approx(
        d_yfi.balanceOf(whale), rel=5 * 10e-4
    ) == d_yfi_to_distribute / (14 * 24)
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert gauge.queuedRewards() == 0


def test_withdraw(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    create_vault,
    create_gauge,
    gov,
    ve_yfi_d_yfi_pool,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.withdraw(True, sender=whale)

    assert pytest.approx(
        d_yfi.balanceOf(whale), rel=5 * 10e-4
    ) == d_yfi_to_distribute / (14 * 24)
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert gauge.queuedRewards() == 0


def test_kick(create_vault, create_gauge, panda, yfi, ve_yfi, whale, gov):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
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
    gauge.withdraw(int(lp_amount / 100), panda, panda, False, sender=panda)
    assert gauge.boostedBalanceOf(whale) != gauge.nextBoostedBalanceOf(whale)
    gauge.kick([whale], sender=panda)

    assert (
        gauge.nextBoostedBalanceOf(whale)
        == gauge.boostedBalanceOf(whale)
        != gauge.balanceOf(whale)
    )


def withdraw_for(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    panda,
    create_vault,
    create_gauge,
    gov,
    ve_yfi_d_yfi_pool,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.approve(panda, lp_amount, sender=whale)

    gauge.withdraw(lp_amount, whale, panda, True, False, sender=panda)

    assert pytest.approx(
        d_yfi.balanceOf(whale), rel=5 * 10e-4
    ) == d_yfi_to_distribute / (14 * 24)
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert gauge.queuedRewards() == 0


def transfer(
    yfi,
    d_yfi,
    ve_yfi,
    whale,
    panda,
    create_vault,
    create_gauge,
    gov,
    ve_yfi_d_yfi_pool,
):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
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

    d_yfi_to_distribute = 10**16
    d_yfi.mint(gov, d_yfi_to_distribute, sender=gov)
    d_yfi.approve(gauge, d_yfi_to_distribute, sender=gov)

    gauge.queueNewRewards(d_yfi_to_distribute, sender=gov)
    assert pytest.approx(gauge.rewardRate()) == d_yfi_to_distribute / (14 * 24 * 3600)
    chain.pending_timestamp += 3600
    gauge.approve(panda, lp_amount, sender=whale)

    gauge.transferFrom(whale, panda, lp_amount, sender=panda)
    gauge.getReward(sender=whale)

    assert gauge.boostedBalance(whale) == 0
    assert pytest.approx(
        d_yfi.balanceOf(whale), rel=5 * 10e-4
    ) == d_yfi_to_distribute / (14 * 24)
    assert d_yfi.balanceOf(ve_yfi_d_yfi_pool) == 0
    assert gauge.queuedRewards() == 0
