import ape
import pytest

DAY_LENGTH = 24 * 60 * 60
WEEK_LENGTH = 7 * DAY_LENGTH
EPOCH_LENGTH = 2 * WEEK_LENGTH
UNIT = 10**18
MAX = 2**256 - 1
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def controller(accounts):
    return accounts[3]

@pytest.fixture
def implementation(project, deployer):
    return project.GaugeV2.deploy(sender=deployer)

@pytest.fixture
def factory(project, deployer, controller, implementation):
    factory = project.GaugeFactory.deploy(controller, sender=deployer)
    factory.set_implementation(implementation, sender=deployer)
    return factory

@pytest.fixture
def controller(chain, project, deployer):
    return project.GaugeController.deploy(chain.pending_timestamp - EPOCH_LENGTH, ZERO_ADDRESS, ZERO_ADDRESS, ZERO_ADDRESS, ZERO_ADDRESS, sender=deployer)

@pytest.fixture
def registry(project, deployer, controller, factory):
    registry = project.GaugeRegistry.deploy(controller, factory, sender=deployer)
    controller.set_whitelister(registry, sender=deployer)
    return registry

def test_register(project, deployer, alice, factory, controller, registry):
    vault = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=deployer).return_value

    # only management can register a gauge
    with ape.reverts():
        registry.register(gauge, sender=alice)

    assert registry.vault_count() == 0
    assert registry.vaults(0) == ZERO_ADDRESS
    assert registry.vault_gauge_map(vault) == ZERO_ADDRESS
    with ape.reverts():
        registry.gauges(0)
    assert not registry.registered(gauge)
    assert not controller.gauge_whitelisted(gauge)
    assert registry.register(gauge, sender=deployer).return_value == 0
    assert registry.vault_count() == 1
    assert registry.vaults(0) == vault
    assert registry.vault_gauge_map(vault) == gauge
    assert registry.gauges(0) == gauge
    assert registry.registered(gauge)
    assert controller.gauge_whitelisted(gauge)

    # cant register same gauge again
    with ape.reverts():
        registry.register(gauge, sender=deployer)

    # cant register different gauge for same vault
    gauge2 = factory.deploy_gauge(vault, b"", sender=deployer).return_value
    with ape.reverts():
        registry.register(gauge2, sender=deployer)

def test_register_wrong_factory(project, deployer, controller, implementation, registry):
    # cant register gauge not originating from the factory
    factory2 = project.GaugeFactory.deploy(controller, sender=deployer)
    factory2.set_implementation(implementation, sender=deployer)
    vault = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory2.deploy_gauge(vault, b"", sender=deployer).return_value

    with ape.reverts():
        registry.register(gauge, sender=deployer)

def test_deregister(project, deployer, alice, factory, controller, registry):
    vault = project.MockVaultToken.deploy(sender=deployer)
    vault2 = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=deployer).return_value
    gauge2 = factory.deploy_gauge(vault2, b"", sender=deployer).return_value
    registry.register(gauge, sender=deployer)
    registry.register(gauge2, sender=deployer)

    # only management can deregister a gauge
    with ape.reverts():
        registry.deregister(gauge, 0, sender=alice)

    # cannot deregister by supplying incorrect index
    with ape.reverts():
        registry.deregister(gauge, 1, sender=deployer)

    assert registry.vault_count() == 2
    assert registry.vaults(0) == vault
    assert registry.vaults(1) == vault2
    registry.deregister(gauge, 0, sender=deployer)
    assert registry.vault_count() == 1
    assert registry.vaults(0) == vault2
    assert registry.vaults(1) == ZERO_ADDRESS
    assert registry.vault_gauge_map(vault) == ZERO_ADDRESS
    with ape.reverts():
        registry.gauges(1)
    assert not registry.registered(gauge)
    assert not controller.gauge_whitelisted(gauge)

def test_deregister_last(project, deployer, factory, controller, registry):
    # deregistering the last entry works as expected
    vault = project.MockVaultToken.deploy(sender=deployer)
    vault2 = project.MockVaultToken.deploy(sender=deployer)
    gauge = factory.deploy_gauge(vault, b"", sender=deployer).return_value
    gauge2 = factory.deploy_gauge(vault2, b"", sender=deployer).return_value
    registry.register(gauge, sender=deployer)
    registry.register(gauge2, sender=deployer)

    registry.deregister(gauge2, 1, sender=deployer)
    assert registry.vault_count() == 1
    assert registry.vaults(0) == vault
    assert registry.vaults(1) == ZERO_ADDRESS
    assert registry.vault_gauge_map(vault2) == ZERO_ADDRESS
    assert not registry.registered(gauge2)
    assert not controller.gauge_whitelisted(gauge2)

def test_set_controller(deployer, alice, controller, registry):
    # only management can set controller
    with ape.reverts():
        registry.set_controller(alice, sender=alice)

    assert registry.controller() == controller
    registry.set_controller(alice, sender=deployer)
    assert registry.controller() == alice

def test_set_controller(deployer, alice, factory, registry):
    # only management can set factory
    with ape.reverts():
        registry.set_factory(alice, sender=alice)

    assert registry.factory() == factory
    registry.set_factory(alice, sender=deployer)
    assert registry.factory() == alice

def test_transfer_management(deployer, alice, bob, registry):
    assert registry.management() == deployer
    assert registry.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        registry.set_management(alice, sender=alice)
    
    registry.set_management(alice, sender=deployer)
    assert registry.pending_management() == alice

    with ape.reverts():
        registry.accept_management(sender=bob)

    registry.accept_management(sender=alice)
    assert registry.management() == alice
    assert registry.pending_management() == ZERO_ADDRESS
