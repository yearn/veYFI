# @version 0.3.7

interface CurvePoolInterface:
    def price_oracle() -> uint256: view

implements: CurvePoolInterface

chainlink_price: uint256
curve_price: uint256
updated: uint256

@external
def set_price(_chainlink: uint256, _curve: uint256):
    self.chainlink_price = _chainlink
    self.curve_price = _curve

@external
def set_updated(_updated: uint256 = block.timestamp):
    self.updated = _updated

@external
@view
def latestRoundData() -> (uint80, int256, uint256, uint256, uint80):
    updated: uint256 = self.updated
    if updated == 0:
        updated = block.timestamp
    return (0, convert(self.chainlink_price, int256), updated, updated, 0)

@external
@view
def price_oracle() -> uint256:
    return self.curve_price
