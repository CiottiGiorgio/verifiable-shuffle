import math
from collections.abc import Iterator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from smart_contracts.verifiable_giveaway.contract import (
    binary_logarithm,
)
from tests.consts import LOG_PRECISION


@pytest.fixture()
def context() -> Iterator[AlgopyTestContext]:
    with algopy_testing_context() as ctx:
        yield ctx


@pytest.mark.parametrize("n,log_n", [(2**i, i) for i in range(64)])
def test_perfect_binary_logarithm(n: int, log_n: int) -> None:
    """Makes sure that the AVM approximated log2 of a perfect power of two is always exactly correct."""
    result = binary_logarithm(algopy.UInt64(n), algopy.UInt64(LOG_PRECISION))

    assert result == log_n << LOG_PRECISION


@pytest.mark.parametrize(
    "n,relative_error",
    [
        (2**2 - 1, 0.06),
        (10, 0.02),
        (2**4 - 1, 0.004),
        (2**5 - 1, 0.004),
        (2**6 - 1, 0.001),
        (100, 0.001),
        (2**7 - 1, 0.001),
        (1000, 0.00008),
    ],
)
def test_small_binary_logarithm(n: int, relative_error: float) -> None:
    """Makes sure that the AVM approximated log2 of a small integer (<= 1_000) is within a known good relative error."""
    result = binary_logarithm(algopy.UInt64(n), LOG_PRECISION)

    expected_log = int(math.log2(n) * 2**16)
    assert abs(expected_log - result.value) / expected_log <= relative_error


@pytest.mark.parametrize(
    "n",
    [
        2**10 - 1,
        2**16 - 1,
        2**32 - 1,
        2**63 - 1,
    ],
)
def test_large_binary_logarithm(n: int) -> None:
    """Makes sure that the AVM approximated log2 of a large integer (> 1_000) is within a known good relative error."""
    result = binary_logarithm(algopy.UInt64(n), algopy.UInt64(LOG_PRECISION))

    expected_log = int(math.log2(n) * 2**LOG_PRECISION)
    assert abs(expected_log - result.value) / expected_log <= 0.000005
