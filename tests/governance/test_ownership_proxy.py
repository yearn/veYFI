import ape
import pytest

UNIT = 1_000_000_000_000_000_000
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def proxy(project, deployer):
    return project.OwnershipProxy.deploy(sender=deployer)

def test_execute(project, deployer, alice, proxy):
    token = project.MockToken.deploy(sender=deployer)
    token.mint(proxy, UNIT, sender=deployer)
    assert token.balanceOf(proxy) == UNIT
    assert token.balanceOf(alice) == 0

    # test privilege
    data = token.transfer.encode_input(alice, UNIT)
    with ape.reverts():
        proxy.execute(token, data, sender=alice)

    proxy.execute(token, data, sender=deployer)
    assert token.balanceOf(proxy) == 0
    assert token.balanceOf(alice) == UNIT

def test_transfer_management(deployer, alice, bob, proxy):
    # cant call directly
    with ape.reverts():
        proxy.set_management(alice, sender=deployer)
    with ape.reverts():
        proxy.set_management(alice, sender=alice)
    assert proxy.management() == deployer.address

    # set management
    data = proxy.set_management.encode_input(alice)
    proxy.execute(proxy, data, sender=deployer)
    assert proxy.management() == alice.address
