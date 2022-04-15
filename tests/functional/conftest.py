import pytest

from eth_utils import to_checksum_address

DAY = 86400
WEEK = 7 * DAY


@pytest.fixture(scope="session")
def gov(accounts):
    yield accounts[0]


@pytest.fixture(scope="session")
def whale_amount():
    yield 10**22


@pytest.fixture(scope="session")
def whale(accounts, yfi, whale_amount):
    a = accounts[1]
    yfi.mint(a, whale_amount, sender=a)
    yield a


@pytest.fixture(scope="session")
def shark_amount():
    yield 10**20


@pytest.fixture(scope="session")
def shark(accounts, yfi, shark_amount):
    a = accounts[2]
    yfi.mint(a, shark_amount, sender=a)
    yield a


@pytest.fixture(scope="session")
def fish_amount():
    yield 10**18


@pytest.fixture(scope="session")
def fish(accounts, yfi, fish_amount):
    a = accounts[3]
    yfi.mint(a, fish_amount, sender=a)
    yield a


@pytest.fixture(scope="session")
def panda(accounts):
    yield accounts[4]


@pytest.fixture(scope="session")
def doggie(accounts):
    yield accounts[5]


@pytest.fixture(scope="session")
def bunny(accounts):
    yield accounts[6]


@pytest.fixture(scope="session")
def yfi(project, gov):
    yield gov.deploy(project.Token, "YFI")


@pytest.fixture(scope="session")
def create_token(project, gov):
    def create_token(name):
        return gov.deploy(project.Token, name)

    yield create_token


@pytest.fixture(scope="session")
def ve_yfi(project, yfi, gov):
    yield gov.deploy(project.VotingEscrow, yfi, "veYFI", "veYFI")


@pytest.fixture(scope="session", autouse=True)
def ve_yfi_rewards(create_ve_yfi_rewards):
    yield create_ve_yfi_rewards()


@pytest.fixture()
def create_ve_yfi_rewards(project, ve_yfi, yfi, gov, chain):
    def create_ve_yfi_rewards():
        chain.pending_timestamp += (
            chain.blocks.head.timestamp // WEEK + 1
        ) * WEEK - chain.blocks.head.timestamp
        chain.mine()

        ve_yfi_rewards = gov.deploy(
            project.VeYfiRewards, ve_yfi, chain.pending_timestamp, yfi, gov, gov
        )
        ve_yfi.set_reward_pool(ve_yfi_rewards, sender=gov)
        return ve_yfi_rewards

    yield create_ve_yfi_rewards


@pytest.fixture(scope="session")
def gauge_factory(project, gov):
    gauge = gov.deploy(project.Gauge)
    extra_reward = gov.deploy(project.ExtraReward)
    yield gov.deploy(project.GaugeFactory, gauge, extra_reward)


@pytest.fixture(scope="session")
def registry(project, gov, ve_yfi, yfi, gauge_factory, ve_yfi_rewards):
    yield gov.deploy(project.Registry, ve_yfi, yfi, gauge_factory, ve_yfi_rewards)


@pytest.fixture(scope="session")
def create_vault(project, gov):
    def create_vault():
        return gov.deploy(project.Token, "Yearn vault")

    yield create_vault


@pytest.fixture(scope="session")
def create_gauge(registry, gauge_factory, gov, project):
    def create_gauge(vault):
        tx = registry.addVaultToRewards(vault, gov, gov, sender=gov)
        gauge_address = next(tx.decode_logs(gauge_factory.GaugeCreated)).gauge
        # TODO: Remove `to_checksum_address` once log decoding returns correct format
        return project.Gauge.at(to_checksum_address(gauge_address))

    yield create_gauge


@pytest.fixture(scope="session")
def create_extra_reward(gauge_factory, gov, project):
    def create_extra_reward(gauge, token):
        tx = gauge_factory.createExtraReward(gauge, token, gov, sender=gov)
        reward_address = next(
            tx.decode_logs(gauge_factory.ExtraRewardCreated)
        ).extraReward
        # TODO: Remove `to_checksum_address` once log decoding returns correct format
        return project.ExtraReward.at(to_checksum_address(reward_address))

    yield create_extra_reward
