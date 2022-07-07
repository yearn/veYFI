import ape
import pytest
from ape import chain, project


def test_gauge_get_reward_for(
    yfi, ve_yfi, whale, whale_amount, shark, create_vault, create_gauge, gov, zap
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

    chain.pending_timestamp += 3600

    gauge.setApprovals(zap, True, False, sender=whale)
    assert yfi.balanceOf(whale) == 0
    zap.claim([gauge.address], False, False, sender=whale)
    assert yfi.balanceOf(whale) != 0
