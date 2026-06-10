import pytest
from math import sqrt
import random

UNIT = 10**18

@pytest.fixture
def math(project, accounts):
    return project.Math.deploy(sender=accounts[0])

def test_sqrt(math):
    for _ in range(1_000):
        v = random.uniform(0, 40_000)
        expected = sqrt(v)
        actual = math.sqrt(int(v*UNIT))/UNIT
        assert abs(actual-expected) < actual / 10**12

def test_decay(math):
    for v in range(60):
        expected = 0.5**(v/60)
        actual = math.decay(v)/10**27
        assert abs(actual-expected) < actual / 10**12
