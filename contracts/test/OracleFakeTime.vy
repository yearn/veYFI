# @version 0.3.7

interface AggregatorV3Interface:
    def latestRoundData() -> (uint80, int256, uint256, uint256, uint80): view

PRICE_FEED: immutable(AggregatorV3Interface) 

@external
def __init__():
    PRICE_FEED = AggregatorV3Interface(0x7c5d4F8345e66f68099581Db340cd65B078C41f4)

@external
def latestRoundData() -> (uint80, int256, uint256, uint256, uint80):
    round_id: uint80 = 0
    price: int256 = 0
    started_at: uint256 = 0
    updated_at: uint256 = 0
    answered_in_round: uint80 = 0
    (round_id, price, started_at, updated_at, answered_in_round) = PRICE_FEED.latestRoundData()
    return (round_id, price, started_at, block.timestamp, answered_in_round)
