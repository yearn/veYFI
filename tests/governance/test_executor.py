import ape
import pytest

UNIT = 1_000_000_000_000_000_000
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
ACCESS_NONE = 0
ACCESS_WHITELIST = 1
ACCESS_BLACKLIST = 2

@pytest.fixture
def proxy(project, deployer):
    return project.OwnershipProxy.deploy(sender=deployer)

@pytest.fixture
def executor(project, deployer, alice, bob, proxy):
    executor = project.Executor.deploy(proxy, sender=deployer)
    data = proxy.set_management.encode_input(executor)
    proxy.execute(proxy, data, sender=deployer)
    assert not executor.governors(alice)
    executor.set_governor(alice, True, sender=deployer)
    assert executor.governors(alice)
    executor.set_governor(bob, True, sender=deployer)
    executor.set_governor(deployer, False, sender=deployer)
    return executor

@pytest.fixture
def token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

def test_execute_single(deployer, alice, proxy, executor, token):
    token.mint(proxy, UNIT, sender=deployer)
    data = token.transfer.encode_input(alice, UNIT)
    assert token.balanceOf(proxy) == UNIT
    assert token.balanceOf(alice) == 0

    # deployer is not a governor
    with ape.reverts():
        executor.execute_single(token, data, sender=deployer)

    # alice is a governor
    executor.execute_single(token, data, sender=alice)
    assert token.balanceOf(proxy) == 0
    assert token.balanceOf(alice) == UNIT

def test_execute_single_whitelist(deployer, alice, bob, proxy, executor, token):
    token.mint(proxy, 2 * UNIT, sender=deployer)
    data = token.transfer.encode_input(deployer, UNIT)
    selector = data[:4].hex()

    # cannot set invalid access flag
    with ape.reverts():
        executor.set_access(token, selector, 3, sender=deployer)

    # enable whitelist for token transfer
    assert not executor.has_whitelist(token, selector)
    assert not executor.has_blacklist(token, selector)
    executor.set_access(token, selector, ACCESS_WHITELIST, sender=deployer)
    assert executor.has_whitelist(token, selector)
    assert not executor.has_blacklist(token, selector)

    # alice is not on whitelist
    assert not executor.is_whitelisted(token, selector, alice)
    with ape.reverts():
        executor.execute_single(token, data, sender=alice)

    # add alice to whitelist
    executor.whitelist(token, selector, alice, True, sender=deployer)
    assert executor.is_whitelisted(token, selector, alice)

    # alice is on whitelist
    executor.execute_single(token, data, sender=alice)
    assert token.balanceOf(deployer) == UNIT

    # bob is not on whitelist
    with ape.reverts():
        executor.execute_single(token, data, sender=bob)

    # remove alice's whitelist
    executor.whitelist(token, selector, alice, False, sender=deployer)
    assert not executor.is_whitelisted(token, selector, alice)
    with ape.reverts():
        executor.execute_single(token, data, sender=alice)

    # disable whitelist
    executor.set_access(token, selector, 0, sender=deployer)
    assert not executor.has_whitelist(token, selector)

    # bob can execute now
    executor.execute_single(token, data, sender=bob)
    assert token.balanceOf(deployer) == 2 * UNIT

def test_execute_single_blacklist(deployer, alice, bob, proxy, executor, token):
    token.mint(proxy, 4 * UNIT, sender=deployer)
    data = token.transfer.encode_input(deployer, UNIT)
    selector = data[:4].hex()

    # enable blacklist for token transfer
    assert not executor.has_whitelist(token, selector)
    assert not executor.has_blacklist(token, selector)
    executor.set_access(token, selector, ACCESS_BLACKLIST, sender=deployer)
    assert not executor.has_whitelist(token, selector)
    assert executor.has_blacklist(token, selector)

    # alice is not on blacklist
    assert not executor.is_blacklisted(token, selector, alice)
    executor.execute_single(token, data, sender=alice)
    assert token.balanceOf(deployer) == UNIT

    # add alice to blacklist
    executor.blacklist(token, selector, alice, True, sender=deployer)
    assert executor.is_blacklisted(token, selector, alice)

    # alice is on blacklist
    with ape.reverts():
        executor.execute_single(token, data, sender=alice)

    # bob isn't on blacklist
    executor.execute_single(token, data, sender=bob)
    assert token.balanceOf(deployer) == 2 * UNIT

    # add bob to blacklist
    executor.blacklist(token, selector, bob, True, sender=deployer)
    
    # remove alice's blacklist
    executor.blacklist(token, selector, alice, False, sender=deployer)
    assert not executor.is_blacklisted(token, selector, alice)
    executor.execute_single(token, data, sender=alice)
    assert token.balanceOf(deployer) == 3 * UNIT

    # disable blacklist
    executor.set_access(token, selector, 0, sender=deployer)
    assert not executor.has_whitelist(token, selector)

    # bob can execute now
    executor.execute_single(token, data, sender=bob)
    assert token.balanceOf(deployer) == 4 * UNIT

def test_execute(deployer, alice, proxy, executor, token):
    mint = token.mint.encode_input(proxy, UNIT)
    transfer = token.transfer.encode_input(alice, UNIT)
    script = executor.script(token, mint) + executor.script(token, transfer)

    # deployer is not a governor
    with ape.reverts():
        executor.execute(script, sender=deployer)

    # alice is a governor
    assert token.balanceOf(token) == 0
    assert token.balanceOf(alice) == 0
    executor.execute(script, sender=alice)
    assert token.balanceOf(token) == 0
    assert token.balanceOf(alice) == UNIT

def test_execute_whitelist(deployer, alice, bob, proxy, executor, token):
    mint = token.mint.encode_input(proxy, UNIT)
    transfer = token.transfer.encode_input(alice, UNIT)
    script = executor.script(token, mint) + executor.script(token, transfer)
    selector = transfer[:4].hex()
    mint_selector = mint[:4].hex()

    # enable whitelist for transfer
    executor.set_access(token, selector, ACCESS_WHITELIST, sender=deployer)
    with ape.reverts():
        executor.execute(script, sender=alice)

    # add alice to whitelist
    executor.whitelist(token, selector, alice, True, sender=deployer)
    executor.execute(script, sender=alice)
    assert token.balanceOf(alice) == UNIT

    # bob is not on whitelist
    with ape.reverts():
        executor.execute(script, sender=bob)

    # enable whitelist for mint
    executor.set_access(token, mint_selector, ACCESS_WHITELIST, sender=deployer)
    with ape.reverts():
        executor.execute(script, sender=alice)

    # add alice to mint function whitelist
    executor.whitelist(token, mint_selector, alice, True, sender=deployer)
    executor.execute(script, sender=alice)
    assert token.balanceOf(alice) == 2 * UNIT

    # remove alice from whitelist
    executor.whitelist(token, selector, alice, False, sender=deployer)
    with ape.reverts():
        executor.execute(script, sender=alice)
    
    # disable whitelist
    executor.set_access(token, selector, ACCESS_NONE, sender=deployer)
    executor.execute(script, sender=alice)
    assert token.balanceOf(alice) == 3 * UNIT

def test_execute_blacklist(deployer, alice, bob, proxy, executor, token):
    mint = token.mint.encode_input(proxy, UNIT)
    transfer = token.transfer.encode_input(alice, UNIT)
    script = executor.script(token, mint) + executor.script(token, transfer)
    selector = transfer[:4].hex()
    mint_selector = mint[:4].hex()

    # enable blacklist for token transfer
    executor.set_access(token, selector, ACCESS_BLACKLIST, sender=deployer)
    executor.execute(script, sender=alice)
    assert token.balanceOf(alice) == UNIT

    # add alice to blacklist
    executor.blacklist(token, selector, alice, True, sender=deployer)
    with ape.reverts():
        executor.execute(script, sender=alice)

    # enable blacklist for token mint
    executor.set_access(token, mint_selector, ACCESS_BLACKLIST, sender=deployer)
    executor.execute(script, sender=bob)
    assert token.balanceOf(alice) == 2 * UNIT

    # add alice to mint blacklist
    executor.blacklist(token, mint_selector, alice, True, sender=deployer)
    with ape.reverts():
        executor.execute(script, sender=alice)

    # remove alice from transfer blacklist
    executor.blacklist(token, selector, alice, False, sender=deployer)
    with ape.reverts():
        executor.execute(script, sender=alice)

    # remove alice from mint blacklist
    executor.blacklist(token, mint_selector, alice, False, sender=deployer)
    executor.execute(script, sender=alice)
    assert token.balanceOf(alice) == 3 * UNIT

def test_transfer_management(deployer, alice, bob, executor):
    assert executor.management() == deployer.address
    assert executor.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        executor.set_management(alice, sender=alice)
    
    executor.set_management(alice, sender=deployer)
    assert executor.pending_management() == alice.address

    with ape.reverts():
        executor.accept_management(sender=bob)

    executor.accept_management(sender=alice)
    assert executor.management() == alice.address
    assert executor.pending_management() == ZERO_ADDRESS

def test_transfer_management_proxy(deployer, alice, proxy, executor):
    executor.set_management(proxy, sender=deployer)
    data = executor.accept_management.encode_input()
    executor.execute_single(executor, data, sender=alice)
    assert executor.management() == proxy.address

def test_management_proxy(deployer, alice, bob, proxy, executor, token):
    executor.set_management(proxy, sender=deployer)
    executor.execute_single(executor, executor.accept_management.encode_input(), sender=alice)

    # add transfer function to whitelist
    token.mint(proxy, UNIT, sender=deployer)
    data = token.transfer.encode_input(deployer, UNIT)
    selector = data[:4].hex()
    enable_whitelist = executor.set_access.encode_input(token, selector, ACCESS_WHITELIST)
    whitelist = executor.whitelist.encode_input(token, selector, alice, True)
    script = executor.script(executor, enable_whitelist) + executor.script(executor, whitelist)
    executor.execute(script, sender=alice)

    with ape.reverts():
        executor.execute_single(token, data, sender=bob)
    
    executor.execute_single(token, data, sender=alice)
    assert token.balanceOf(deployer) == UNIT