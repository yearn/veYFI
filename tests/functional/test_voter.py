import brownie
import pytest
from brownie import ZERO_ADDRESS, chain, Gauge


def test_vote(
    yfi,
    ve_yfi,
    whale,
    shark,
    whale_amount,
    shark_amount,
    voter,
    create_vault,
    create_gauge,
):
    vault_a = create_vault()
    create_gauge(vault_a)
    vault_b = create_vault()
    create_gauge(vault_b)

    voter.vote([vault_a, vault_b], [1, 2], {"from": whale})
    assert voter.totalWeight() == 0
    assert voter.usedWeights(whale) == 0
    assert pytest.approx(voter.weights(vault_a)) == 0
    assert pytest.approx(voter.weights(vault_b)) == 0

    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})

    yfi.approve(ve_yfi, shark_amount, {"from": shark})
    ve_yfi.create_lock(shark_amount, chain.time() + 3600 * 24 * 365, {"from": shark})

    assert voter.usedWeights(whale) == 0

    voter.vote([vault_a], [1], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert voter.weights(vault_a) == ve_yfi.balanceOf(whale)

    with brownie.reverts("!=length"):
        voter.vote([vault_a, vault_b], [1], {"from": whale})

    voter.vote([vault_b], [1], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert voter.weights(vault_a) == 0
    assert voter.weights(vault_b) == ve_yfi.balanceOf(whale)

    voter.vote([vault_a, vault_b], [1, 2], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.weights(vault_a)) == ve_yfi.balanceOf(whale) / 3
    assert pytest.approx(voter.weights(vault_b)) == ve_yfi.balanceOf(whale) * 2 / 3

    voter.vote([vault_a], [1], {"from": shark})

    assert pytest.approx(voter.totalWeight()) == ve_yfi.balanceOf(
        whale
    ) + ve_yfi.balanceOf(shark)
    assert pytest.approx(voter.weights(vault_a)) == ve_yfi.balanceOf(
        whale
    ) / 3 + ve_yfi.balanceOf(shark)


def test_vote_delegation(
    yfi,
    ve_yfi,
    whale,
    shark,
    whale_amount,
    shark_amount,
    voter,
    create_vault,
    create_gauge,
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    voter.delegate(shark, True, {"from": whale})
    assert voter.getDelegated(shark) == [whale]
    assert voter.delegation(whale) == shark

    yfi.approve(ve_yfi, shark_amount, {"from": shark})
    ve_yfi.create_lock(shark_amount, chain.time() + 3600 * 24 * 365, {"from": shark})

    vault_a = create_vault()
    create_gauge(vault_a)

    assert voter.usedWeights(whale) == 0
    voter.vote([whale, shark], [vault_a], [1], {"from": shark})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale) + ve_yfi.balanceOf(shark)
    whaleBalanceOf = ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(shark) == ve_yfi.balanceOf(shark)
    assert voter.weights(vault_a) == ve_yfi.balanceOf(whale) + ve_yfi.balanceOf(shark)

    voter.delegate(ZERO_ADDRESS, False, {"from": whale})
    assert voter.delegation(whale) == ZERO_ADDRESS
    assert voter.getDelegated(shark) == []

    assert voter.usedWeights(whale) == whaleBalanceOf
    with brownie.reverts("!=length"):
        voter.vote([whale, shark], [1], {"from": shark})


def test_remove_vault_from_rewards(
    ve_yfi, yfi, whale_amount, whale, create_vault, create_gauge, voter, gov
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})

    vault_a = create_vault()
    tx = create_gauge(vault_a)
    gauge_a = Gauge.at(tx.events["GaugeCreated"]["gauge"])

    vault_b = create_vault()
    tx = create_gauge(vault_b)

    voter.vote([vault_a], [1], {"from": whale})
    voter.removeVaultFromRewards(vault_a)
    assert voter.gauges(vault_a) == ZERO_ADDRESS
    assert voter.isGauge(gauge_a) == False
    assert voter.vaultForGauge(gauge_a) == ZERO_ADDRESS
    assert voter.getVaults() == [vault_b]
    assert voter.usedWeights(whale) != 0
    assert voter.weights(vault_a) == voter.usedWeights(whale)
    voter.vote([vault_a], [1], {"from": whale})
    assert voter.weights(vault_a) == 0
    assert voter.usedWeights(whale) == 0


def test_poke(yfi, ve_yfi, whale, whale_amount, voter, create_vault, create_gauge):
    vault_a = create_vault()
    create_gauge(vault_a)
    vault_b = create_vault()
    create_gauge(vault_b)

    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(
        whale_amount / 2, chain.time() + 3600 * 24 * 365, {"from": whale}
    )

    voter.vote([vault_a, vault_b], [1, 2], {"from": whale})
    assert pytest.approx(voter.totalWeight()) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.usedWeights(whale)) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.weights(vault_a)) == ve_yfi.balanceOf(whale) / 3
    assert pytest.approx(voter.weights(vault_b)) == ve_yfi.balanceOf(whale) * 2 / 3

    ve_yfi.increase_amount(whale_amount / 2, {"from": whale})
    voter.poke(whale, {"from": whale})

    assert pytest.approx(voter.totalWeight()) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.usedWeights(whale)) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.weights(vault_a)) == ve_yfi.balanceOf(whale) / 3
    assert pytest.approx(voter.weights(vault_b)) == ve_yfi.balanceOf(whale) * 2 / 3


def test_reset_voter(
    yfi, ve_yfi, whale, whale_amount, voter, create_vault, create_gauge
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})

    vault_a = create_vault()
    create_gauge(vault_a)
    vault_b = create_vault()
    create_gauge(vault_b)

    voter.vote([vault_a, vault_b], [1, 2], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.weights(vault_a)) == ve_yfi.balanceOf(whale) / 3
    assert pytest.approx(voter.weights(vault_b)) == ve_yfi.balanceOf(whale) * 2 / 3

    voter.reset({"from": whale})
    assert voter.totalWeight() == 0
    assert voter.usedWeights(whale) == 0
    assert voter.weights(vault_a) == 0
    assert voter.weights(vault_b) == 0


def test_set_gov(voter, gov, panda):
    with brownie.reverts("!authorized"):
        voter.setGov(panda, {"from": panda})
    with brownie.reverts("zero address"):
        voter.setGov(ZERO_ADDRESS, {"from": gov})
    voter.setGov(panda, {"from": gov})
    assert voter.gov() == panda
