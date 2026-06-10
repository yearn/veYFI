# @version 0.3.10

UNIT: constant(uint256) = 10**18
MINUTE_FACTOR: constant(uint256) = 988_514_020_352_896_135_356_867_505
DECAY_SCALE: constant(uint256) = 10**27

@external
@pure
def sqrt(_x: uint256) -> uint256:
    if _x == 0:
        return 0

    x: uint256 = unsafe_mul(_x, UNIT)
    r: uint256 = 1
    if x >= 1 << 128:
        x = x >> 128
        r = r << 64
    if x >= 1 << 64:
        x = x >> 64
        r = r << 32
    if x >= 1 << 32:
        x = x >> 32
        r = r << 16
    if x >= 1 << 16:
        x = x >> 16
        r = r << 8
    if x >= 1 << 8:
        x = x >> 8
        r = r << 4
    if x >= 1 << 4:
        x = x >> 4
        r = r << 2
    if x >= 1 << 2:
        r = r << 1

    x = unsafe_mul(_x, UNIT)
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1
    r = unsafe_add(r, unsafe_div(x,  r)) >> 1

    d: uint256 = x / r

    if r >= d:
        return d
    return r

@external
@pure
def decay(_m: uint256) -> uint256:
    m: uint256 = _m
    f: uint256 = DECAY_SCALE
    x: uint256 = MINUTE_FACTOR
    if m % 2 != 0:
        f = MINUTE_FACTOR

    for _ in range(7):
        m /= 2
        if m == 0:
            break
        x = x * x / DECAY_SCALE
        if m % 2 != 0:
            f = f * x / DECAY_SCALE

    return f
