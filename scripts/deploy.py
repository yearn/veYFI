from pathlib import Path
from readline import append_history_file

import click
from ape import accounts, project, chain
from ape.cli import NetworkBoundCommand, network_option, account_option
from eth._utils.address import generate_contract_address
from eth_utils import to_checksum_address, to_canonical_address


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_ve_yfi(network, account):
    yfi = account.deploy(project.Token, "yfi")
    # deploy veYFI
    reward_pool_address = to_checksum_address(
        generate_contract_address(
            to_canonical_address(str(accounts[0])), accounts[0].nonce + 1
        )
    )
    veyfi = project.VotingYFI.deploy(yfi, reward_pool_address, sender=accounts[0])
    start_time = (
        chain.pending_timestamp + 7 * 3600 * 24
    )  # MUST offset by a week otherwise token distributed are lost since no lock has been made yet.
    reward_pool = project.RewardPool.deploy(veyfi, start_time, sender=accounts[0])
    assert str(reward_pool) == reward_pool_address, "broken setup"
