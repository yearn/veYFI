import brownie
import pytest
from brownie import ZERO_ADDRESS, chain


def test_delegate(
    vote_delegation, yfi, ve_yfi, ve_yfi_rewards, whale_amount, whale, shark, panda
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    vote_delegation.delegate(shark, {"from": whale})
    assert vote_delegation.getDelegated(shark) == [whale]
    delegation = vote_delegation.delegation(whale).dict()
    assert delegation["to"] == shark
    assert delegation["until"] == 0
    assert vote_delegation.getDelegated(shark) == [whale]

    vote_delegation.removeDelegation({"from": whale})
    delegation = vote_delegation.delegation(whale).dict()
    assert delegation["to"] == ZERO_ADDRESS
    assert delegation["until"] == 0
    assert vote_delegation.getDelegated(shark) == []

    until = chain.time() + 3600
    vote_delegation.delegate(shark, until, {"from": whale})
    delegation = vote_delegation.delegation(whale).dict()
    assert delegation["to"] == shark
    assert delegation["until"] == until
    assert vote_delegation.getDelegated(shark) == [whale]

    with brownie.reverts("can't change delegation"):
        vote_delegation.removeDelegation({"from": whale})

    with brownie.reverts("can't change delegation"):
        vote_delegation.delegate(panda, {"from": whale})
    chain.sleep(3600 + 10)

    vote_delegation.delegate(panda, {"from": whale})
    delegation = vote_delegation.delegation(whale).dict()
    assert delegation["to"] == panda
    assert delegation["until"] == 0

    until = chain.time() + 3600
    vote_delegation.delegate(panda, until, {"from": whale})
    with brownie.reverts("must increase"):
        vote_delegation.increaseDelegationDuration(0)

    vote_delegation.increaseDelegationDuration(until + 10, {"from": whale})
    delegation = vote_delegation.delegation(whale).dict()
    assert delegation["to"] == panda
    assert delegation["until"] == until + 10


def test_delegate_gas(
    vote_delegation, yfi, ve_yfi, ve_yfi_rewards, whale_amount, whale, panda
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    # assert(False)
    vote_delegation.delegate(panda, {"from": whale})  # gas used: 97738


def test_delegate_gas_10(
    accounts, yfi, ve_yfi, ve_yfi_rewards, whale, panda, fish_amount, vote_delegation
):
    for i in range(10):
        accounts.add()
        yfi.mint(accounts[-1], fish_amount)
        yfi.approve(ve_yfi, fish_amount, {"from": accounts[-1]})
        ve_yfi.create_lock(
            fish_amount, chain.time() + 3600 * 24 * 365, {"from": accounts[-1]}
        )

    for i in range(11, 20):
        vote_delegation.delegate(panda, {"from": accounts[i]})

    # assert(False)
    vote_delegation.delegate(whale, {"from": accounts[19]})  # gas used: 101626

    accounts = accounts[:10]


def test_delegate_gas_100(
    accounts, yfi, ve_yfi, ve_yfi_rewards, whale, panda, fish_amount, vote_delegation
):
    for i in range(100):
        accounts.add()
        yfi.mint(accounts[-1], fish_amount)
        yfi.approve(ve_yfi, fish_amount, {"from": accounts[-1]})
        ve_yfi.create_lock(
            fish_amount, chain.time() + 3600 * 24 * 365, {"from": accounts[-1]}
        )

    for i in range(11, 110):
        vote_delegation.delegate(panda, {"from": accounts[i]})

    # assert(False)
    vote_delegation.delegate(whale, {"from": accounts[109]})  # gas used: 269476

    accounts = accounts[:10]


@pytest.mark.skip(reason="really slows down the test suite")
def test_delegate_gas_1000(
    accounts, yfi, ve_yfi, ve_yfi_rewards, whale, panda, fish_amount, vote_delegation
):
    for i in range(1000):
        accounts.add()
        yfi.mint(accounts[-1], fish_amount)
        yfi.approve(ve_yfi, fish_amount, {"from": accounts[-1]})
        ve_yfi.create_lock(
            fish_amount, chain.time() + 3600 * 24 * 365, {"from": accounts[-1]}
        )

    for i in range(11, 1010):
        vote_delegation.delegate(panda, {"from": accounts[i]})

    tx = vote_delegation.removeDelegation({"from": accounts[1009]})
    assert tx.gas_usage < 2_000_000
