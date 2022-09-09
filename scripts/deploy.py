from pathlib import Path
from readline import append_history_file

import click
from ape import accounts, project, chain
from ape.cli import NetworkBoundCommand, network_option, account_option
from eth._utils.address import generate_contract_address
from eth_utils import to_checksum_address, to_canonical_address
from datetime import datetime

@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_veyfi(network, account):
    now = datetime.now()
    yfi = "0x6bD8a96197bfe16a2BA8e492318CcbA655A74077" # Testnet
    # deploy veYFI
    reward_pool_address = to_checksum_address(
        generate_contract_address(
            to_canonical_address(str(account)), account.nonce + 1
        )
    )
    veyfi = account.deploy(project.VotingYFI, yfi, reward_pool_address, required_confirmations=0)
    start_time = (
        int(datetime.timestamp(now)) + 7 * 3600 * 24
    )  # MUST offset by a week otherwise token distributed are lost since no lock has been made yet.
    reward_pool = account.deploy(project.RewardPool, veyfi, start_time, required_confirmations=0)
    print(reward_pool)
    print(reward_pool_address)
    assert str(reward_pool) == reward_pool_address, "broken setup"
