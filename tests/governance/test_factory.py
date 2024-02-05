import ape
import pytest

DAY_LENGTH = 24 * 60 * 60
WEEK_LENGTH = 7 * DAY_LENGTH
EPOCH_LENGTH = 2 * WEEK_LENGTH
UNIT = 10**18
MAX = 2**256 - 1
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

LEGACY_GAUGES = [
    '0x0000000000000000000000000000000000000001',
    '0x0000000000000000000000000000000000000002',
    '0x0000000000000000000000000000000000000003',
]

@pytest.fixture
def controller(accounts):
    return accounts[3]

@pytest.fixture
def factory(project, deployer, controller):
    return project.GaugeFactory.deploy(controller, sender=deployer)

@pytest.fixture
def implementation(project, deployer):
    return project.GaugeV2.deploy(sender=deployer)

def test_deploy(project, deployer, alice, bob, controller, factory, implementation):
    factory.set_implementation(implementation, sender=deployer)
    factory.set_gauge_owner(bob, sender=deployer)
    vault = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=alice).return_value
    gauge = project.GaugeV2.at(gauge)
    assert factory.gauge_versions(gauge) == 2
    assert gauge.asset() == vault
    assert gauge.owner() == bob
    assert gauge.controller() == controller

def test_set_implementation(deployer, alice, factory, implementation):
    # only management can set implementation
    with ape.reverts():
        factory.set_implementation(implementation, sender=alice)

    assert factory.version() == 1
    assert factory.implementation() == ZERO_ADDRESS
    factory.set_implementation(implementation, sender=deployer)
    assert factory.version() == 2
    assert factory.implementation() == implementation

def test_set_gauge_owner(project, deployer, alice, factory, implementation):
    factory.set_implementation(implementation, sender=deployer)

    # only management can set gauge owner
    with ape.reverts():
        factory.set_gauge_owner(alice, sender=alice)

    assert factory.gauge_owner() == deployer
    factory.set_gauge_owner(alice, sender=deployer)
    assert factory.gauge_owner() == alice

    vault = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=alice).return_value
    gauge = project.GaugeV2.at(gauge)
    assert gauge.owner() == alice

def test_set_controller(project, deployer, alice, controller, factory, implementation):
    factory.set_implementation(implementation, sender=deployer)

    # only management can set controller
    with ape.reverts():
        factory.set_controller(alice, sender=alice)

    assert factory.controller() == controller
    factory.set_controller(alice, sender=deployer)
    assert factory.controller() == alice
    
    vault = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=alice).return_value
    gauge = project.GaugeV2.at(gauge)
    assert gauge.controller() == alice

def test_legacy_gauges(project, deployer, alice, factory, implementation):
    # only management can set legacy gauges
    with ape.reverts():
        factory.set_legacy_gauges(LEGACY_GAUGES, sender=alice)

    for gauge in LEGACY_GAUGES:
        assert factory.gauge_versions(gauge) == 0
    factory.set_legacy_gauges(LEGACY_GAUGES, sender=deployer)
    for gauge in LEGACY_GAUGES:
        assert factory.gauge_versions(gauge) == 1

    # cant overwrite version of existing gauge
    factory.set_implementation(implementation, sender=deployer)
    vault = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=alice).return_value

    with ape.reverts():
        factory.set_legacy_gauges([gauge], sender=deployer)

def test_transfer_management(deployer, alice, bob, factory):
    assert factory.management() == deployer
    assert factory.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        factory.set_management(alice, sender=alice)
    
    factory.set_management(alice, sender=deployer)
    assert factory.pending_management() == alice

    with ape.reverts():
        factory.accept_management(sender=bob)

    factory.accept_management(sender=alice)
    assert factory.management() == alice
    assert factory.pending_management() == ZERO_ADDRESS

