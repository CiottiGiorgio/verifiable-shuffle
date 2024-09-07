import base64
import hashlib
from typing import List, Tuple

import algokit_utils
import pytest
from algokit_utils import (
    DeployResponse,
    EnsureBalanceParameters,
    LogicError,
    TransactionParameters,
    get_localnet_default_account,
)
from algokit_utils.beta.account_manager import AddressAndSigner
from algokit_utils.beta.algorand_client import AlgorandClient
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

import smart_contracts.mock_randomness_beacon.config as cfg_rb
import smart_contracts.verifiable_shuffle.config as cfg_vs
import smart_contracts.verifiable_shuffle.errors as err
from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
    MockRandomnessBeaconClient,
)
from smart_contracts.artifacts.verifiable_shuffle.verifiable_shuffle_client import (
    VerifiableShuffleClient,
)


@pytest.fixture(scope="session")
def mock_randomness_beacon_deployment(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> DeployResponse:
    config.configure(
        debug=False,
        # trace_all=True,
    )

    client = MockRandomnessBeaconClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    return client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.Fail,
        on_update=algokit_utils.OnUpdate.AppendApp,
        template_values={
            cfg_rb.OUTPUT: hashlib.sha3_256(b"NOT-SO-RANDOM-DATA").digest()
        },
    )


@pytest.fixture(scope="session")
def verifiable_shuffle_client(
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
    mock_randomness_beacon_deployment: DeployResponse,
) -> VerifiableShuffleClient:
    client = VerifiableShuffleClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
        template_values={
            cfg_vs.RANDOMNESS_BEACON: mock_randomness_beacon_deployment.app.app_id,
            cfg_vs.SAFETY_GAP: 1,
            "COMMIT_OPUP_SCALING_COST_CONSTANT": 700,
            "REVEAL_OPUP_SCALING_COST_CONSTANT": 600,
        },
    )

    client.create_bare()
    return client


@pytest.fixture(scope="session")
def user_account(algorand_client: AlgorandClient) -> AddressAndSigner:
    acct = algorand_client.account.random()

    algokit_utils.ensure_funded(
        algorand_client.client.algod,
        EnsureBalanceParameters(
            account_to_fund=acct.address, min_spending_balance_micro_algos=10_000_000
        ),
    )

    return acct


# These test cases are not derived from a reference implementation but rather just used to detect instability
#  in the algorithm.
@pytest.mark.parametrize(
    "test_scenario",
    [
        (2, 1, [2]),
        (2, 2, [2, 1]),
        (5, 2, [4, 2]),
        (10, 3, [4, 1, 5]),
        (10, 9, [4, 1, 5, 2, 6, 10, 3, 7, 8]),
        (10, 10, [4, 1, 5, 2, 6, 10, 3, 7, 8, 9]),
        (80, 1, [34]),
        (80, 5, [34, 20, 9, 25, 22]),
        (
            80,
            20,
            [34, 20, 9, 25, 22, 55, 14, 8, 7, 15, 2, 61, 24, 42, 75, 70, 36, 3, 43, 78],
        ),
        (
            2**8 - 1,
            16,
            [54, 160, 6, 130, 75, 4, 126, 207, 249, 103, 90, 134, 121, 86, 127, 165],
        ),
        (2**16 - 1, 8, [65079, 39278, 24202, 18094, 24361, 54080, 9978, 5055]),
        (2**32 - 2, 4, [146095708, 3969517345, 3683389089, 196699750]),
    ],
)
def test_sequence(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    mock_randomness_beacon_deployment: DeployResponse,
    user_account: AddressAndSigner,
    test_scenario: Tuple[int, int, List[int]],
) -> None:
    participants, winners, shuffled_winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = 100_000

    commit_result = verifiable_shuffle_client.opt_in_commit(
        delay=1,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address, suggested_params=sp
        ),
    )

    assert commit_result.confirmed_round

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = 100_000

    reveal_result = verifiable_shuffle_client.close_out_reveal(
        transaction_parameters=TransactionParameters(
            signer=user_account.signer,
            sender=user_account.address,
            suggested_params=sp,
            foreign_apps=[mock_randomness_beacon_deployment.app.app_id],
        )
    )
    reveal_outcome = reveal_result.return_value

    assert (
        base64.b32encode(bytes(reveal_outcome.commitment_tx_id)).decode().strip("=")
        == commit_result.tx_id
    )
    assert reveal_outcome.winners == shuffled_winners


@pytest.mark.parametrize(
    "test_scenario",
    [
        (2**32 - 2, 4),
        (2**16 - 1, 8),
        (2**8 - 1, 16),
        (80, 20),
        (47, 25),
        (35, 30),
    ],
)
def test_safety_bounds(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    user_account: AddressAndSigner,
    test_scenario: Tuple[int, int],
) -> None:
    participants, winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = 100_000

    with pytest.raises(LogicError, match=err.SAFE_SIZE):
        verifiable_shuffle_client.opt_in_commit(
            delay=1,
            participants=participants,
            winners=winners + 1,
            transaction_parameters=TransactionParameters(
                signer=user_account.signer,
                sender=user_account.address,
                suggested_params=sp,
            ),
        )

    verifiable_shuffle_client.opt_in_commit(
        delay=1,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address, suggested_params=sp
        ),
    )

    verifiable_shuffle_client.clear_state(
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address
        )
    )


# We can't test that this will fail for winners+1 because that would mean we have more winners than
#  participants.
@pytest.mark.parametrize(
    "test_scenario",
    [
        (34, 34),
    ],
)
def test_special_case(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    user_account: AddressAndSigner,
    test_scenario: Tuple[int, int],
) -> None:
    participants, winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = 100_000

    verifiable_shuffle_client.opt_in_commit(
        delay=1,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address, suggested_params=sp
        ),
    )

    verifiable_shuffle_client.clear_state(
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address
        )
    )
