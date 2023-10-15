struct LatestRoundData:
    round_id: uint80
    answer: int256
    started: uint256
    updated: uint256
    answered_round: uint80

interface ChainlinkOracle:
    def latestRoundData() -> LatestRoundData: view
    def decimals() -> uint256: view

SCALE: constant(int256) = 10**18

yfi_oracle: public(immutable(ChainlinkOracle)) # YFI/USD
eth_oracle: public(immutable(ChainlinkOracle)) # ETH/USD
decimals: public(constant(uint256)) = 18

@external
def __init__(_yfi_oracle: address, _eth_oracle: address):
    yfi_oracle = ChainlinkOracle(_yfi_oracle)
    eth_oracle = ChainlinkOracle(_eth_oracle)
    assert ChainlinkOracle(_yfi_oracle).decimals() == 8
    assert ChainlinkOracle(_eth_oracle).decimals() == 8

@external
@view
def latestRoundData() -> LatestRoundData:
    yfi: LatestRoundData = yfi_oracle.latestRoundData()
    eth: LatestRoundData = eth_oracle.latestRoundData()
    if eth.updated < yfi.updated:
        yfi.updated = eth.updated
    yfi.answer = yfi.answer * SCALE / eth.answer
    return yfi
