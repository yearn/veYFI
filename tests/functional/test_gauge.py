from pathlib import Path
import brownie

import pytest
from brownie import chain, Gauge


def test_change_reward_manager(
    create_vault,
    create_gauge,
    panda,
    gov,
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    with brownie.reverts():
        gauge.updateRewardManager(panda, {"from": panda})

    gauge.updateRewardManager(panda, {"from": gov})
    assert gauge.rewardManager() == panda


def test_do_not_queue_zero_rewards(create_vault, create_gauge, panda):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    with brownie.reverts():
        gauge.queueNewRewards(0, {"from": panda})


def test_donate(create_vault, create_gauge, yfi, whale):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfi.approve(gauge, 10 ** 18, {"from": whale})
    gauge.donate(10 ** 18, {"from": whale})

    assert gauge.queuedRewards() == 10 ** 18


def test_sweep(create_vault, create_gauge, create_token, yfi, whale, gov):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")
    yfo.mint(gauge, 10 ** 18)
    with brownie.reverts("!authorized"):
        gauge.sweep(yfo, {"from": whale})
    with brownie.reverts("!rewardToken"):
        gauge.sweep(yfi, {"from": gov})
    with brownie.reverts("!stakingToken"):
        gauge.sweep(vault, {"from": gov})
    gauge.sweep(yfo, {"from": gov})
    assert yfo.balanceOf(gov) == 10 ** 18
