import ape
import pytest

from eth_utils import keccak, to_checksum_address


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def test_delegate(
    chain, vote_delegation, yfi, ve_yfi, whale_amount, whale, shark, panda
):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    vote_delegation.delegate(shark, sender=whale)
    # TODO: `tuple(...)` hack until https://github.com/ApeWorX/ape/issues/573
    assert vote_delegation.getDelegated(shark) == tuple([whale])
    # TODO: refactor after https://github.com/ApeWorX/ape/issues/574
    delegation = vote_delegation.delegation(whale)  # .dict()
    assert delegation[0] == shark  # "to"
    assert delegation[1] == 0  # "until"
    # TODO: `tuple(...)` hack until https://github.com/ApeWorX/ape/issues/573
    assert vote_delegation.getDelegated(shark) == tuple([whale])

    vote_delegation.removeDelegation(sender=whale)
    # TODO: refactor after https://github.com/ApeWorX/ape/issues/574
    delegation = vote_delegation.delegation(whale)  # .dict()
    assert delegation[0] == ZERO_ADDRESS  # "to"
    assert delegation[1] == 0  # "until"
    # TODO: `tuple(...)` hack until https://github.com/ApeWorX/ape/issues/573
    assert vote_delegation.getDelegated(shark) == tuple([])

    until = chain.pending_timestamp + 3600
    vote_delegation.delegate(shark, until, sender=whale)
    # TODO: refactor after https://github.com/ApeWorX/ape/issues/574
    delegation = vote_delegation.delegation(whale)  # .dict()
    assert delegation[0] == shark  # "to"
    assert delegation[1] == until  # "until"
    # TODO: `tuple(...)` hack until https://github.com/ApeWorX/ape/issues/573
    assert vote_delegation.getDelegated(shark) == tuple([whale])

    with ape.reverts("can't change delegation"):
        vote_delegation.removeDelegation(sender=whale)

    with ape.reverts("can't change delegation"):
        vote_delegation.delegate(panda, sender=whale)
    chain.pending_timestamp += 3600 + 10

    vote_delegation.delegate(panda, sender=whale)
    # TODO: refactor after https://github.com/ApeWorX/ape/issues/574
    delegation = vote_delegation.delegation(whale)  # .dict()
    assert delegation[0] == panda  # "to"
    assert delegation[1] == 0  # "until"

    until = chain.pending_timestamp + 3600
    vote_delegation.delegate(panda, until, sender=whale)
    with ape.reverts("must increase"):
        vote_delegation.increaseDelegationDuration(0, sender=whale)

    vote_delegation.increaseDelegationDuration(until + 10, sender=whale)
    # TODO: refactor after https://github.com/ApeWorX/ape/issues/574
    delegation = vote_delegation.delegation(whale)  # .dict()
    assert delegation[0] == panda  # "to"
    assert delegation[1] == until + 10  # "until"


def test_delegate_gas(chain, vote_delegation, yfi, ve_yfi, whale_amount, whale, panda):
    yfi.approve(ve_yfi, whale_amount, sender=whale)
    ve_yfi.create_lock(
        whale_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=whale
    )
    tx = vote_delegation.delegate(panda, sender=whale)
    assert tx.gas_used < 120_000


def random_address(i):
    # deterministically "random" account from integer seed
    return to_checksum_address(keccak(i.to_bytes(32, "big"))[:20])


# TODO: try 1000 when using faster provider
@pytest.mark.parametrize("num_accounts", [10, 100])
def test_many_delegates_gas_usage(
    accounts,
    chain,
    yfi,
    ve_yfi,
    gov,
    panda,
    fish_amount,
    vote_delegation,
    num_accounts,
):
    delegating_accounts = []
    for i in range(num_accounts):
        account = accounts[random_address(i)]
        delegating_accounts.append(account)
        yfi.mint(account, fish_amount, sender=gov)
        yfi.approve(ve_yfi, fish_amount, sender=account)
        ve_yfi.create_lock(
            fish_amount, chain.pending_timestamp + 3600 * 24 * 365, sender=account
        )

    for account in delegating_accounts:
        vote_delegation.delegate(panda, sender=account)

    # NOTE: Using last account from the loop
    tx = vote_delegation.removeDelegation(sender=account)

    assert tx.gas_used < 2_000_000
