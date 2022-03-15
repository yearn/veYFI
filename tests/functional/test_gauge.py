import brownie
from brownie import Gauge, ExtraReward, ZERO_ADDRESS, chain


def test_set_reward_manager(create_vault, create_gauge, panda, gov):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    with brownie.reverts("_rewardManager 0x0 address"):
        gauge.setRewardManager(ZERO_ADDRESS, {"from": gov})
    with brownie.reverts("!authorized"):
        gauge.setRewardManager(panda, {"from": panda})

    gauge.setRewardManager(panda, {"from": gov})
    assert gauge.rewardManager() == panda

    gauge.setRewardManager(gov, {"from": panda})
    assert gauge.rewardManager() == gov


def test_set_gov(create_vault, create_gauge, panda, gov):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    with brownie.reverts("Ownable: new owner is the zero address"):
        gauge.transferOwnership(ZERO_ADDRESS, {"from": gov})
    with brownie.reverts("Ownable: caller is not the owner"):
        gauge.transferOwnership(panda, {"from": panda})

    gauge.transferOwnership(panda, {"from": gov})
    assert gauge.owner() == panda


def test_do_not_queue_zero_rewards(create_vault, create_gauge, panda):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    with brownie.reverts("==0"):
        gauge.queueNewRewards(0, {"from": panda})


def test_sweep(create_vault, create_gauge, create_token, yfi, whale, gov):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")
    yfo.mint(gauge, 10**18)
    with brownie.reverts("Ownable: caller is not the owner"):
        gauge.sweep(yfo, {"from": whale})
    with brownie.reverts("protected token"):
        gauge.sweep(yfi, {"from": gov})
    with brownie.reverts("protected token"):
        gauge.sweep(vault, {"from": gov})
    gauge.sweep(yfo, {"from": gov})
    assert yfo.balanceOf(gov) == 10**18


def test_add_extra_reward(
    create_vault, create_gauge, create_token, create_extra_reward, gov, panda
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")

    tx = create_extra_reward(gauge, yfo)
    extra_reward = ExtraReward.at(tx.events["ExtraRewardCreated"]["extraReward"])
    with brownie.reverts("!authorized"):
        gauge.addExtraReward(extra_reward, {"from": panda})
    with brownie.reverts("!reward setting"):
        gauge.addExtraReward(ZERO_ADDRESS, {"from": gov})

    gauge.addExtraReward(extra_reward, {"from": gov})
    assert gauge.extraRewardsLength() == 1


def test_remove_extra_reward(
    create_vault, create_gauge, create_token, create_extra_reward, gov, panda
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")
    yfp = create_token("YFP")

    yfo_tx = create_extra_reward(gauge, yfo)
    yfo_extra_reward = ExtraReward.at(
        yfo_tx.events["ExtraRewardCreated"]["extraReward"]
    )
    with brownie.reverts("extra reward not found"):
        gauge.removeExtraReward(yfo_extra_reward, {"from": gov})
    gauge.addExtraReward(yfo_extra_reward, {"from": gov})

    yfp_tx = create_extra_reward(gauge, yfp)
    yfp_extra_reward = ExtraReward.at(
        yfp_tx.events["ExtraRewardCreated"]["extraReward"]
    )
    gauge.addExtraReward(yfp_extra_reward, {"from": gov})
    assert gauge.extraRewardsLength() == 2

    with brownie.reverts("!authorized"):
        gauge.removeExtraReward(yfp_extra_reward, {"from": panda})

    gauge.removeExtraReward(yfp_extra_reward, {"from": gov})
    gauge.removeExtraReward(yfo_extra_reward, {"from": gov})
    assert gauge.extraRewardsLength() == 0


def test_clear_extra_rewards(
    create_vault, create_gauge, create_token, create_extra_reward, gov
):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfo = create_token("YFO")
    yfp = create_token("YFP")

    yfo_tx = create_extra_reward(gauge, yfo)
    yfo_extra_reward = ExtraReward.at(
        yfo_tx.events["ExtraRewardCreated"]["extraReward"]
    )
    gauge.addExtraReward(yfo_extra_reward, {"from": gov})

    yfp_tx = create_extra_reward(gauge, yfp)
    yfp_extra_reward = ExtraReward.at(
        yfp_tx.events["ExtraRewardCreated"]["extraReward"]
    )
    gauge.addExtraReward(yfp_extra_reward, {"from": gov})
    assert gauge.extraRewardsLength() == 2

    gauge.clearExtraRewards({"from": gov})
    assert gauge.extraRewardsLength() == 0


def test_small_queued_rewards_duration_extension(create_vault, create_gauge, yfi, gov):
    vault = create_vault()
    tx = create_gauge(vault)
    gauge = Gauge.at(tx.events["GaugeCreated"]["gauge"])
    yfi_to_distribute = 10**20
    yfi.mint(gov, yfi_to_distribute * 2)
    yfi.approve(gauge, yfi_to_distribute * 2, {"from": gov})

    gauge.queueNewRewards(yfi_to_distribute, {"from": gov})
    finish = gauge.periodFinish()
    # distribution started, do not extend the duration unless rewards are 120% of what has been distributed.
    chain.sleep(24 * 3600)
    # Should have distributed 1/7, adding 1% will not trigger an update.
    gauge.queueNewRewards(10**18, {"from": gov})
    assert gauge.queuedRewards() == 10**18
    assert gauge.periodFinish() == finish
    chain.sleep(10)

    # If more than 120% of what has been distributed is queued -> make a new period
    gauge.queueNewRewards(10**20 / 7 * 1.2, {"from": gov})
    assert finish != gauge.periodFinish()
    assert gauge.periodFinish() != finish
