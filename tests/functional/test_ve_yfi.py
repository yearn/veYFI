from pathlib import Path

import pytest
from brownie import chain


def test_create_lock(yfi, ve_yfi, whale, whale_amount, ve_yfi_rewards):
    yfi.approve(ve_yfi, whale_amount, {"from": whale})
    ve_yfi.create_lock(whale_amount, chain.time() + 3600 * 24 * 365, {"from": whale})
