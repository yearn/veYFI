import ape
import pytest
from ape import chain
import math

SLIPPAGE_TOLERANCE = 3
SLIPPAGE_DENOMINATOR = 1000
AMOUNT = 10**18
# contract constants
DISCOUNT_TABLE = []
MAX = 500
NUMERATOR = 10000

for i in range(1, MAX + 1):
    d = 1.0 / (1.0 + (9.9999 * (math.e ** (4.6969 * (i / MAX - 1)))))
    DISCOUNT_TABLE.append(int(d * NUMERATOR))


@pytest.mark.parametrize("percent_locked", [1, 10, 40, 70])
def test_exercise(o_yfi, yfi, ve_yfi, options, gov, panda, percent_locked):
    # Lock tokens to reach the targeted percentage of locked tokens
    total_to_mint = 10**22
    yfi.mint(gov, total_to_mint, sender=gov)
    to_lock = int(total_to_mint * percent_locked / 100)
    yfi.approve(ve_yfi, to_lock, sender=gov)
    assert yfi.balanceOf(ve_yfi) == 0
    ve_yfi.modify_lock(
        to_lock, chain.blocks.head.timestamp + 3600 * 24 * 14, sender=gov
    )

    yfi.transfer(options, AMOUNT, sender=gov)
    o_yfi.mint(panda, AMOUNT, sender=gov)
    estimate = options.eth_required(AMOUNT)
    assert (
        pytest.approx(
            int(
                options.get_latest_price()
                * DISCOUNT_TABLE[percent_locked * 5]
                / NUMERATOR
            )
        )
        == estimate
    )
    o_yfi.approve(options, AMOUNT, sender=panda)
    assert yfi.balanceOf(panda) == 0
    options.exercise(AMOUNT, sender=panda, value=estimate)
    assert yfi.balanceOf(panda) == AMOUNT


def test_slippage_tollerance(o_yfi, yfi, options, gov, panda):
    yfi.mint(options, AMOUNT * 2, sender=gov)
    o_yfi.mint(panda, AMOUNT * 2, sender=gov)
    estimate = options.eth_required(AMOUNT)
    o_yfi.approve(options, AMOUNT * 2, sender=panda)
    assert yfi.balanceOf(panda) == 0
    with ape.reverts("price out of tolerance"):
        options.exercise(
            AMOUNT,
            sender=panda,
            value=estimate - estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR - 1,
        )
    options.exercise(
        AMOUNT,
        sender=panda,
        value=estimate - estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR,
    )
    assert yfi.balanceOf(panda) == AMOUNT
    with ape.reverts("price out of tolerance"):
        options.exercise(
            AMOUNT,
            sender=panda,
            value=estimate + estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR + 1,
        )
    options.exercise(
        AMOUNT,
        sender=panda,
        value=estimate + estimate * SLIPPAGE_TOLERANCE // SLIPPAGE_DENOMINATOR,
    )
    assert yfi.balanceOf(panda) == 2 * AMOUNT


def test_kill(o_yfi, yfi, options, gov, panda):
    yfi.balanceOf(gov) == 0
    o_yfi.mint(panda, AMOUNT * 2, sender=gov)
    yfi.mint(options, AMOUNT, sender=gov)
    options.kill(sender=gov)
    yfi.balanceOf(gov) == 1
    estimate = options.eth_required(AMOUNT)
    o_yfi.approve(options, AMOUNT, sender=panda)
    with ape.reverts("killed"):
        options.exercise(AMOUNT, sender=panda, value=estimate)


def test_sweep(o_yfi, yfi, options, gov, panda):
    o_yfi.mint(options, AMOUNT, sender=gov)
    yfi.mint(options, AMOUNT, sender=gov)
    options.sweep(o_yfi, sender=gov)
    assert o_yfi.balanceOf(gov) == AMOUNT
    with ape.reverts("protected token"):
        options.sweep(yfi, sender=gov)
