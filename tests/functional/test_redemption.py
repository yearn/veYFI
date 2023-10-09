import ape
import pytest
from math import exp

SLIPPAGE_TOLERANCE = 3
SLIPPAGE_DENOMINATOR = 1000
AMOUNT = 10**18


def discount(s, x):
    return 1 / (1 + 10 * exp(4.7 * (s * x - 1)))


@pytest.mark.parametrize("percent_locked", [1, 5, 10, 40, 60])
@pytest.mark.parametrize("scaling_factor", [1, 2, 4, 8, 10])
def test_redeem(
    chain, d_yfi, yfi, ve_yfi, redemption, gov, panda, percent_locked, scaling_factor
):
    redemption.start_ramp(scaling_factor * AMOUNT, 0, sender=gov)
    # Lock tokens to reach the targeted percentage of locked tokens
    assert yfi.totalSupply() == 0
    total_to_mint = 10**22
    yfi.mint(gov, total_to_mint, sender=gov)
    to_lock = int(total_to_mint * percent_locked / 100)
    yfi.approve(ve_yfi, to_lock, sender=gov)
    ve_yfi.modify_lock(
        to_lock, chain.blocks.head.timestamp + 3600 * 24 * 2000, sender=gov
    )

    expected = discount(scaling_factor, percent_locked / 100)
    assert pytest.approx(expected) == redemption.discount() / AMOUNT

    yfi.transfer(redemption, AMOUNT, sender=gov)
    d_yfi.mint(panda, AMOUNT, sender=gov)
    expected = int(redemption.get_latest_price() * (1 - expected))
    assert pytest.approx(expected) == redemption.eth_required(AMOUNT)
    d_yfi.approve(redemption, AMOUNT, sender=panda)
    assert yfi.balanceOf(panda) == 0
    redemption.redeem(AMOUNT, sender=panda, value=expected)
    assert yfi.balanceOf(panda) == AMOUNT


def test_slippage_tollerance(d_yfi, yfi, redemption, gov, panda):
    yfi.mint(redemption, AMOUNT * 2, sender=gov)
    d_yfi.mint(panda, AMOUNT * 2, sender=gov)
    estimate = redemption.eth_required(AMOUNT)
    d_yfi.approve(redemption, AMOUNT * 2, sender=panda)
    assert yfi.balanceOf(panda) == 0
    with ape.reverts("price out of tolerance"):
        redemption.redeem(
            AMOUNT,
            sender=panda,
            value=estimate - estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR - 1,
        )
    redemption.redeem(
        AMOUNT,
        sender=panda,
        value=estimate - estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR,
    )
    assert yfi.balanceOf(panda) == AMOUNT
    with ape.reverts("price out of tolerance"):
        redemption.redeem(
            AMOUNT,
            sender=panda,
            value=estimate + estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR + 1,
        )
    redemption.redeem(
        AMOUNT,
        sender=panda,
        value=estimate + estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR,
    )
    assert yfi.balanceOf(panda) == 2 * AMOUNT


def test_ramp(chain, redemption, gov, panda):
    assert redemption.scaling_factor() == AMOUNT
    assert redemption.scaling_factor_ramp() == (0, 0, AMOUNT, AMOUNT)
    with ape.reverts():
        redemption.start_ramp(2 * AMOUNT, sender=panda)

    ts = chain.pending_timestamp + 10
    redemption.start_ramp(2 * AMOUNT, 1000, ts, sender=gov)
    assert redemption.scaling_factor_ramp() == (ts, ts + 1000, AMOUNT, 2 * AMOUNT)
    chain.pending_timestamp = ts + 200
    chain.mine()
    assert redemption.scaling_factor() == AMOUNT * 12 // 10

    with ape.reverts():
        redemption.start_ramp(3 * AMOUNT, sender=gov)

    with ape.reverts():
        redemption.stop_ramp(sender=panda)

    chain.pending_timestamp = ts + 500
    with chain.isolate():
        redemption.stop_ramp(sender=gov)
        assert redemption.scaling_factor() == AMOUNT * 15 // 10
        assert redemption.scaling_factor_ramp() == (
            0,
            0,
            AMOUNT * 15 // 10,
            AMOUNT * 15 // 10,
        )

    chain.mine()
    assert redemption.scaling_factor() == AMOUNT * 15 // 10
    chain.pending_timestamp = ts + 1000
    chain.mine()
    assert redemption.scaling_factor() == AMOUNT * 2
    chain.pending_timestamp = ts + 2000
    chain.mine()
    assert redemption.scaling_factor() == AMOUNT * 2


def test_kill(d_yfi, yfi, redemption, gov, panda):
    assert yfi.balanceOf(gov) == 0
    d_yfi.mint(panda, AMOUNT * 2, sender=gov)
    yfi.mint(redemption, AMOUNT, sender=gov)
    redemption.kill(sender=gov)
    assert yfi.balanceOf(gov) == AMOUNT
    estimate = redemption.eth_required(AMOUNT)
    d_yfi.approve(redemption, AMOUNT, sender=panda)
    with ape.reverts("killed"):
        redemption.redeem(AMOUNT, sender=panda, value=estimate)


def test_sweep(d_yfi, yfi, redemption, gov):
    d_yfi.mint(redemption, AMOUNT, sender=gov)
    yfi.mint(redemption, AMOUNT, sender=gov)
    redemption.sweep(d_yfi, sender=gov)
    assert d_yfi.balanceOf(gov) == AMOUNT
    with ape.reverts("protected token"):
        redemption.sweep(yfi, sender=gov)
