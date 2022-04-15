import ape
import pytest
from ape import chain

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def test_ve_yfi_claim(yfi, ve_yfi, whale, whale_amount, create_ve_yfi_rewards, gov):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)

    ve_yfi_rewards = create_ve_yfi_rewards()
    yfi.approve(ve_yfi_rewards, rewards, sender=gov)

    chain.pending_timestamp += 3600 * 24
    current_begning_of_week = int(chain.pending_timestamp / (86400 * 7)) * 86400 * 7
    ve_yfi_rewards.checkpoint_total_supply(sender=gov)
    ve_yfi_rewards.queueNewRewards(rewards, sender=gov)

    assert rewards == ve_yfi_rewards.tokens_per_week(current_begning_of_week)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.claim(sender=whale)
    assert yfi.balanceOf(whale) == 0

    chain.pending_timestamp += 3600 * 24 * 7
    chain.mine()
    ve_yfi_rewards.claim(sender=whale)
    assert yfi.balanceOf(whale) == rewards


def test_ve_yfi_claim_for(
    yfi, ve_yfi, whale, fish, whale_amount, create_ve_yfi_rewards, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    rewards = 10**18
    yfi.mint(gov, rewards, sender=gov)

    ve_yfi_rewards = create_ve_yfi_rewards()
    yfi.approve(ve_yfi_rewards, rewards, sender=gov)

    chain.pending_timestamp += 3600 * 24
    current_begning_of_week = int(chain.pending_timestamp / (86400 * 7)) * 86400 * 7
    ve_yfi_rewards.checkpoint_total_supply(sender=gov)
    ve_yfi_rewards.queueNewRewards(rewards, sender=gov)

    assert rewards == ve_yfi_rewards.tokens_per_week(current_begning_of_week)
    chain.pending_timestamp += 3600
    ve_yfi_rewards.claim(sender=whale)
    assert yfi.balanceOf(whale) == 0

    chain.pending_timestamp += 3600 * 24 * 7
    chain.mine()
    ve_yfi_rewards.claim(whale, sender=fish)
    assert yfi.balanceOf(whale) == rewards


def test_recover_balance(
    yfi, ve_yfi, create_ve_yfi_rewards, create_token, whale, whale_amount, gov
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    yfo = create_token("YFO")
    ve_yfi_rewards = create_ve_yfi_rewards()
    yfo.mint(ve_yfi_rewards, 10**18, sender=gov)
    with ape.reverts():
        ve_yfi_rewards.recover_balance(yfo, sender=whale)
    with ape.reverts():
        ve_yfi_rewards.recover_balance(yfi, sender=gov)
    ve_yfi_rewards.recover_balance(yfo, sender=gov)
    assert yfo.balanceOf(gov) == 10**18


def test_set_admin(ve_yfi_rewards, panda, gov):
    with ape.reverts():
        ve_yfi_rewards.commit_admin(panda, sender=panda)
    ve_yfi_rewards.transferOwnership(panda, sender=gov)

    with ape.reverts():
        ve_yfi_rewards.apply_admin(sender=panda)

    ve_yfi_rewards.apply_admin(sender=gov)
    assert ve_yfi_rewards.admin() == panda
