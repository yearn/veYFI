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
