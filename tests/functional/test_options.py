import ape

SLIPPAGE_TOLERANCE = 3
SLIPPAGE_DENOMINATOR = 1000
AMOUNT = 10**18


def test_exercise(o_yfi, yfi, options, gov, panda):
    yfi.mint(options, AMOUNT, sender=gov)
    o_yfi.mint(panda, AMOUNT, sender=gov)
    estimate = options.eth_required(AMOUNT)
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
