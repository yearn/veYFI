from pathlib import Path
import brownie

import pytest
from brownie import chain, Gauge


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
    gov,
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})

    yfi.approve(ve_yfi, shark_amount, {"from": shark})
    ve_yfi.create_lock(shark_amount, chain.time() + 3600 * 24 * 365, {"from": shark})

    vault = create_vault()
    tx = create_gauge(vault)
    gauge_a = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    voter.addVaultToRewards(gauge_a, gov, gov)

    vault = create_vault()
    tx = create_gauge(vault)
    gauge_b = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    voter.addVaultToRewards(gauge_b, gov, gov)

    assert voter.usedWeights(whale) == 0

    voter.vote([gauge_a], [1], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert voter.weights(gauge_a) == ve_yfi.balanceOf(whale)

    with brownie.reverts():
        voter.vote([gauge_a, gauge_b], [1], {"from": whale})

    voter.vote([gauge_b], [1], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert voter.weights(gauge_a) == 0
    assert voter.weights(gauge_b) == ve_yfi.balanceOf(whale)

    voter.vote([gauge_a, gauge_b], [1, 2], {"from": whale})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert pytest.approx(voter.weights(gauge_a)) == ve_yfi.balanceOf(whale) / 3
    assert pytest.approx(voter.weights(gauge_b)) == ve_yfi.balanceOf(whale) * 2 / 3

    voter.vote([gauge_a], [1], {"from": shark})

    assert pytest.approx(voter.totalWeight()) == ve_yfi.balanceOf(
        whale
    ) + ve_yfi.balanceOf(shark)
    assert pytest.approx(voter.weights(gauge_a)) == ve_yfi.balanceOf(
        whale
    ) / 3 + ve_yfi.balanceOf(shark)


from pathlib import Path
import brownie

import pytest
from brownie import chain, Gauge


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
    gov,
):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
    ve_yfi.delegate(shark, {"from": whale})

    yfi.approve(ve_yfi, shark_amount, {"from": shark})
    ve_yfi.create_lock(shark_amount, chain.time() + 3600 * 24 * 365, {"from": shark})

    vault = create_vault()
    tx = create_gauge(vault)
    gauge_a = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    voter.addVaultToRewards(gauge_a, gov, gov)

    assert voter.usedWeights(whale) == 0
    voter.vote([whale, shark], [gauge_a], [1], {"from": shark})
    assert voter.totalWeight() == ve_yfi.balanceOf(whale) + ve_yfi.balanceOf(shark)
    assert voter.usedWeights(whale) == ve_yfi.balanceOf(whale)
    assert voter.usedWeights(shark) == ve_yfi.balanceOf(shark)
    assert voter.weights(gauge_a) == ve_yfi.balanceOf(whale) + ve_yfi.balanceOf(shark)
