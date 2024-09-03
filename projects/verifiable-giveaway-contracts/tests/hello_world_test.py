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


def test_binary_logarithm(context: AlgopyTestContext) -> None:
    # Arrange
    context.set_template_var("LOGARITHM_FRACTIONAL_PRECISION", algopy.UInt64(10))
    result = sum((binary_logarithm(x) + 1) for x in range(61, 81))

    assert result == 1


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
