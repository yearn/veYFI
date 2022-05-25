from pathlib import Path
from brownie import chain, project, accounts, Contract, VeYfiRewards, Gauge , ExtraReward ,GaugeFactory, Token, config, Registry

VaultProject = project.load(
    Path.home() / ".brownie" / "packages" / config["dependencies"][0]
)
VaultRegistry = Vault = VaultProject.Registry

Vault = VaultProject.Vault


def main():
    account = accounts.load("testnet_deploy")
    # yfi = account.deploy(project.Token, "yfi")
    yfi = Contract("0x203e4A13650C5B74f13F13eB9a7387D84a8b3e79")
    # deploy veYFI
    # ve_yfi = account.deploy(project.VotingEscrow, yfi, "veYFI", "veYFI")
    ve_yfi = Contract("0x699480b12043610040660b6dC31eF9d0E4D96385")

    # Only when we have reached a new 2 week period we can deploy what's left, make sure some veYFI has been locked.
    begining_of_week = int(chain.time() / (14 * 86400)) * 14 * 86400
    assert ve_yfi.totalSupply(begining_of_week) > 0
    # ve_yfi_rewards = account.deploy(
    #     VeYfiRewards, ve_yfi, begining_of_week + 1, yfi, account, account
    # )
    ve_yfi_rewards = Contract("0x8f1095bF569EA203E8e91237a41e09e2bb645857")
    # ve_yfi.set_reward_pool(ve_yfi_rewards, {"from": account})

    # deploy gauge Factory
    # gauge = account.deploy(Gauge, publish_source=True)
    gauge = Gauge.at("0x93644d86ec8ef773d4a9ddfff7d8254f0736216d")
    Gauge.publish_source(gauge)
    extra_reward = account.deploy(ExtraReward, publish_source=True)
    gauge_factory = account.deploy(GaugeFactory, gauge, extra_reward, publish_source=True)

    # deploy gauge registry
    registry = account.deploy(
        Registry, ve_yfi, yfi, gauge_factory, ve_yfi_rewards, publish_source=True
    )

    # deploy a vault
    vault_registry = account.deploy(VaultRegistry)

    token = account.deploy(Token, "test token", publish_source=True)
    vault = account.deploy(Vault)
    vault_registry.newRelease(vault, {"from": account})

    vault.initialize(token, account, account, "", "", {"from": account})

    # create gauge
    tx = registry.addVaultToRewards(vault, account, account, {"from": account})
