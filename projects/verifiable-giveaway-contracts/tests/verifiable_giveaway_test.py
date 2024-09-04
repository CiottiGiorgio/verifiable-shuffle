import math
from collections.abc import Iterator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from smart_contracts.verifiable_giveaway.contract import (
    binary_logarithm,
)


@pytest.fixture()
def context() -> Iterator[AlgopyTestContext]:
    with algopy_testing_context() as ctx:
        yield ctx


@pytest.mark.parametrize(
    "n",
    [
        2**1,
        2**2 - 1,
        10,
        2**4 - 1,
        2**5 - 1,
        2**6 - 1,
        100,
        2**7 - 1,
        1000,
        2**10 - 1,
        2**10,
        2**16 - 1,
        2**16,
        2**32 - 1,
        2**32,
        2**63 - 1,
    ],
)
def test_binary_logarithm(n: int) -> None:
    """
    Makes sure that the approximated binary logarithm computed in the AVM is equal
     to the correct one up to the precision we require.
    """
    result = binary_logarithm(algopy.UInt64(n), algopy.UInt64(16))

    expected_log = int(math.log2(n) * 2**16)
    assert abs(expected_log - result.value) / expected_log < 0.001


# def test_reveal(context: AlgopyTestContext) -> None:
#     # Arrange
#     dummy_randomness_beacon = context.any.application(
#         logs=[arc4_prefix(sha3_256(b"NOT-SO-RANDOM-DATA").digest())]
#     )
#
#     context.set_template_var("RANDOMNESS_BEACON_ID", dummy_randomness_beacon.id)
#
#     contract = VerifiableGiveaway()
#     contract.commitment[context.default_sender] = Commitment(
#         tx_id=algopy.arc4.StaticArray[algopy.arc4.Byte, Literal[32]].from_bytes(
#             context.any.bytes(32)
#         ),
#         round=algopy.arc4.UInt64(0),
#         participants=algopy.arc4.UInt32(2),
#         winners=algopy.arc4.UInt8(2),
#     )
#
#     # Act
#     output = contract.reveal()
#
#     # Assert
#     assert output == f"Hello, asd"
