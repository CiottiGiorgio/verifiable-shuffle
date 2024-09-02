from collections.abc import Iterator
from hashlib import sha3_256
from typing import Literal

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context, arc4_prefix

from smart_contracts.verifiable_giveaway.contract import Commitment, VerifiableGiveaway


@pytest.fixture()
def context() -> Iterator[AlgopyTestContext]:
    with algopy_testing_context() as ctx:
        yield ctx


def test_reveal(context: AlgopyTestContext) -> None:
    # Arrange
    dummy_randomness_beacon = context.any.application(
        logs=[arc4_prefix(sha3_256(b"NOT-SO-RANDOM-DATA").digest())]
    )

    context.set_template_var("RANDOMNESS_BEACON_ID", dummy_randomness_beacon.id)

    contract = VerifiableGiveaway()
    contract.commitment[context.default_sender] = Commitment(
        tx_id=algopy.arc4.StaticArray[algopy.arc4.Byte, Literal[32]].from_bytes(
            context.any.bytes(32)
        ),
        round=algopy.arc4.UInt64(0),
        participants=algopy.arc4.UInt32(2),
        winners=algopy.arc4.UInt8(2),
    )

    # Act
    output = contract.reveal()

    # Assert
    # assert output == f"Hello, {dummy_input}"
