import itertools
import math
from collections.abc import Iterator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

import smart_contracts.verifiable_giveaway.config as cfg
from smart_contracts.verifiable_giveaway.contract import (
    k_permutation_logarithm,
)


@pytest.fixture()
def context() -> Iterator[AlgopyTestContext]:
    with algopy_testing_context() as ctx:
        yield ctx


@pytest.mark.parametrize(
    "n,k,relative_error",
    itertools.chain(
        ((2**i, 1, 0.0) for i in range(1, 63)),
        ((2**i, 2, 1e-2) for i in range(1, 63)),
        ((2**i, 3, 1e-2) for i in range(2, 63)),
        ((2**i, 4, 1e-2) for i in range(2, 63)),
        ((2**i, 5, 1e-5) for i in range(3, 63)),
        ((2**i, 7, 1e-6) for i in range(3, 63)),
        ((2**i, 10, 1e-6) for i in range(4, 63)),
        ((2**i, 15, 1e-4) for i in range(4, 63)),
        ((2**i, 20, 1e-6) for i in range(5, 63)),
        ((2**i, 30, 1e-6) for i in range(5, 63)),
        ((2**i, 34, 1e-6) for i in range(6, 63)),
        # The following test vectors are way beyond spec for how we are going to use this subroutine.
        # Nevertheless, it's reassuring that the relative error is still bounded.
        ((2**i, 50, 1e-6) for i in range(6, 63)),
        ((2**i, 75, 1e-6) for i in range(7, 63)),
        ((2**i, 100, 1e-6) for i in range(7, 63)),
        # ((2**i, 1_000, 1e-6) for i in range(10, 63)),  # Too slow to include.
    ),
)
def test_k_permutation_logarithm(n: int, k: int, relative_error: float) -> None:
    """
    Makes sure that the AVM approximated binary logarithm of #k-permutations is within a good known relative error.
    For some selected k, we test some reasonably possible n.
    """
    result = k_permutation_logarithm(
        algopy.UInt64(n), algopy.UInt64(k), algopy.UInt64(cfg.LOG_PRECISION)
    )

    expected_log = int(
        sum(math.log2(i) for i in range(n - k + 1, n + 1)) * 2**cfg.LOG_PRECISION
    )
    assert abs(expected_log - result.value) / expected_log <= relative_error
