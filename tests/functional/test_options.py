import ape
import pytest
from ape import chain

SLIPPAGE_TOLERANCE = 3
SLIPPAGE_DENOMINATOR = 1000
AMOUNT = 10**18
# contract constants
DISCOUNT_TABLE = [
    914,
    912,
    910,
    908,
    906,
    904,
    902,
    900,
    898,
    896,
    894,
    892,
    889,
    887,
    885,
    882,
    880,
    877,
    875,
    872,
    870,
    867,
    864,
    861,
    859,
    856,
    853,
    850,
    847,
    844,
    841,
    837,
    834,
    831,
    828,
    824,
    821,
    817,
    814,
    810,
    807,
    803,
    799,
    795,
    792,
    788,
    784,
    780,
    776,
    772,
    767,
    763,
    759,
    755,
    750,
    746,
    741,
    737,
    732,
    728,
    723,
    718,
    713,
    709,
    704,
    699,
    694,
    689,
    684,
    679,
    674,
    668,
    663,
    658,
    653,
    647,
    642,
    637,
    631,
    626,
    620,
    615,
    609,
    603,
    598,
    592,
    586,
    581,
    575,
    569,
    563,
    558,
    552,
    546,
    540,
    534,
    529,
    523,
    517,
    511,
    505,
    499,
    493,
    487,
    482,
    476,
    470,
    464,
    458,
    452,
    447,
    441,
    435,
    429,
    423,
    418,
    412,
    406,
    401,
    395,
    390,
    384,
    378,
    373,
    367,
    362,
    357,
    351,
    346,
    341,
    335,
    330,
    325,
    320,
    315,
    310,
    305,
    300,
    295,
    290,
    285,
    280,
    276,
    271,
    266,
    262,
    257,
    253,
    248,
    244,
    240,
    235,
    231,
    227,
    223,
    219,
    215,
    211,
    207,
    203,
    199,
    196,
    192,
    188,
    185,
    181,
    178,
    174,
    171,
    168,
    164,
    161,
    158,
    155,
    152,
    149,
    146,
    143,
    140,
    137,
    135,
    132,
    129,
    127,
    124,
    121,
    119,
    117,
    114,
    112,
    109,
    107,
    105,
    103,
    101,
    98,
    96,
    94,
    92,
    90,
]
DISCOUNT_NUMERATOR = 1000


@pytest.fixture(params=[1, 10, 40, 70])
def percent_locked(gov, yfi, ve_yfi, request):
    total_to_mint = 10**22
    yfi.mint(gov, total_to_mint, sender=gov)
    to_lock = int(total_to_mint * request.param / 100)
    yfi.approve(ve_yfi, to_lock, sender=gov)
    assert yfi.balanceOf(ve_yfi) == 0
    ve_yfi.modify_lock(
        to_lock, chain.blocks.head.timestamp + 3600 * 24 * 14, sender=gov
    )
    yield request.param


def test_exercise(o_yfi, yfi, options, gov, panda, percent_locked):
    yfi.transfer(options, AMOUNT, sender=gov)
    o_yfi.mint(panda, AMOUNT, sender=gov)
    estimate = options.eth_required(AMOUNT)
    assert (
        pytest.approx(
            int(
                options.get_latest_price()
                * DISCOUNT_TABLE[percent_locked * 2]
                / DISCOUNT_NUMERATOR
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
