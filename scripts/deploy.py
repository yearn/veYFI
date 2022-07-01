from pathlib import Path
from readline import append_history_file

import click
from ape import accounts, project, chain
from ape.cli import NetworkBoundCommand, network_option, account_option


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def main(network, account):
    yfi = account.deploy(project.Token, "yfi")
    # deploy veYFI
    ve_yfi = account.deploy(project.VotingYFI, yfi, "veYFI", "veYFI")

    # Only when we have reached a new 2 week period we can deploy what's left, make sure some veYFI has been locked.
    begining_of_week = int(chain.pending_timestamp / 14 * 86400) * 14 * 86400
    assert ve_yfi.totalSupply(begining_of_week) > 0

    ve_yfi_rewards = account.deploy(
        project.VeYfiRewards, ve_yfi, chain.pending_timestamp, yfi, account, account
    )
    ve_yfi.set_reward_pool(ve_yfi_rewards, sender=account)

    # deploy gauge Factory
    gauge = account.deploy(project.Gauge)
    extra_reward = account.deploy(project.ExtraReward)
    gauge_factory = account.deploy(project.GaugeFactory, gauge, extra_reward)

    # deploy gauge registry
    registry = account.deploy(
        project.Registry, ve_yfi, yfi, gauge_factory, ve_yfi_rewards
    )

    # deploy a vault
    token = account.deploy(project.Token, "test token")
    vault = account.deploy(project.dependencies["vault"].Vault)
    vault.initialize(token, account, account, "", "", sender=account)

    # create gauge
    tx = registry.addVaultToRewards(vault, account, account, sender=account)
