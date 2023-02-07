import ape
import pytest
from ape import chain

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def test_ve_yfi_claim(yfi, ve_yfi, whale, ve_yfi_rewards, gov):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 86400 * 365, sender=whale
    )
    chain.pending_timestamp += 86400 * 7
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)

    yfi.approve(ve_yfi_rewards, rewards, sender=gov)

    chain.pending_timestamp += 86400
    current_begning_of_week = int(chain.pending_timestamp / (86400 * 7)) * 86400 * 7
    ve_yfi.checkpoint(sender=gov)

    ve_yfi_rewards.checkpoint_total_supply(sender=gov)
    ve_yfi_rewards.burn(rewards, sender=gov)

    assert rewards == ve_yfi_rewards.tokens_per_week(current_begning_of_week)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.claim(sender=whale)
    assert yfi.balanceOf(whale) == 0

    chain.pending_timestamp += 86400 * 14
    chain.mine()
    ve_yfi_rewards.claim(sender=whale)
    assert yfi.balanceOf(whale) == rewards


def test_ve_yfi_claim_for(yfi, ve_yfi, whale, fish, ve_yfi_rewards, gov):
    whale_amount = 10**22
    yfi.mint(whale, whale_amount, sender=whale)
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.modify_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    chain.pending_timestamp += 86400 * 7
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)

    yfi.approve(ve_yfi_rewards, rewards, sender=gov)

    chain.pending_timestamp += 3600 * 24
    current_begning_of_week = int(chain.pending_timestamp / (86400 * 7)) * 86400 * 7

    ve_yfi_rewards.checkpoint_total_supply(sender=gov)
    ve_yfi_rewards.burn(rewards, sender=gov)

    assert rewards == ve_yfi_rewards.tokens_per_week(current_begning_of_week)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.claim(sender=whale)
    assert yfi.balanceOf(whale) == 0

    chain.pending_timestamp += 3600 * 24 * 14
    chain.mine()
    ve_yfi_rewards.claim(whale, sender=fish)
    assert yfi.balanceOf(whale) == rewards
