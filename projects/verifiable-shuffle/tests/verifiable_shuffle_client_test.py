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
from algosdk.constants import min_txn_fee
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
from smart_contracts.artifacts.verifiable_shuffle_opup.verifiable_shuffle_opup_client import (
    VerifiableShuffleOpupClient,
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
def opup_deployment(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> DeployResponse:
    config.configure(
        debug=False,
        # trace_all=True,
    )

    client = VerifiableShuffleOpupClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    return client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.Fail,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )


@pytest.fixture(scope="session")
def verifiable_shuffle_client(
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
    mock_randomness_beacon_deployment: DeployResponse,
    opup_deployment: DeployResponse,
) -> VerifiableShuffleClient:
    client = VerifiableShuffleClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
        template_values={
            cfg_vs.RANDOMNESS_BEACON: mock_randomness_beacon_deployment.app.app_id,
            cfg_vs.OPUP: opup_deployment.app.app_id,
            cfg_vs.SAFETY_GAP: 1,
            cfg_vs.COMMIT_SINGLE_WINNER_OP_COST: 600,
            cfg_vs.REVEAL_SINGLE_WINNER_OP_COST: 500,
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
        (2, 1, [1]),
        (2, 2, [1, 0]),
        (5, 2, [3, 1]),
        (10, 3, [3, 0, 4]),
        (10, 9, [3, 0, 4, 1, 5, 9, 2, 6, 7]),
        (10, 10, [3, 0, 4, 1, 5, 9, 2, 6, 7, 8]),
        (80, 1, [33]),
        (80, 5, [33, 19, 8, 24, 21]),
        (
            80,
            20,
            [33, 19, 8, 24, 21, 54, 13, 7, 6, 14, 1, 60, 23, 41, 74, 69, 35, 2, 42, 77],
        ),
        (
            2**8 - 1,
            16,
            [53, 159, 5, 129, 74, 3, 125, 206, 248, 102, 89, 133, 120, 85, 126, 164],
        ),
        (2**16 - 1, 8, [65078, 39277, 24201, 18093, 24360, 54079, 9977, 5054]),
        (2**32 - 2, 4, [146095707, 3969517344, 3683389088, 196699749]),
    ],
)
def test_sequence(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    mock_randomness_beacon_deployment: DeployResponse,
    opup_deployment: DeployResponse,
    user_account: AddressAndSigner,
    test_scenario: Tuple[int, int, List[int]],
) -> None:
    participants, winners, shuffled_winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = (
        (
            winners
            * verifiable_shuffle_client.app_client.template_values[
                cfg_vs.COMMIT_SINGLE_WINNER_OP_COST
            ]
        )
        // 700
        + 2
    ) * min_txn_fee

    commit_result = verifiable_shuffle_client.opt_in_commit(
        delay=1,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer,
            sender=user_account.address,
            suggested_params=sp,
            foreign_apps=[opup_deployment.app.app_id],
        ),
    )

    assert commit_result.confirmed_round

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = (
        (
            winners
            * verifiable_shuffle_client.app_client.template_values[
                cfg_vs.REVEAL_SINGLE_WINNER_OP_COST
            ]
        )
        // 700
        + 3
    ) * min_txn_fee

    reveal_result = verifiable_shuffle_client.close_out_reveal(
        transaction_parameters=TransactionParameters(
            signer=user_account.signer,
            sender=user_account.address,
            suggested_params=sp,
            foreign_apps=[
                mock_randomness_beacon_deployment.app.app_id,
                opup_deployment.app.app_id,
            ],
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
        (2**32 - 1, 4),
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
    opup_deployment: DeployResponse,
    user_account: AddressAndSigner,
    test_scenario: Tuple[int, int],
) -> None:
    participants, winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = sp.fee = (
        (
            winners
            * verifiable_shuffle_client.app_client.template_values[
                cfg_vs.COMMIT_SINGLE_WINNER_OP_COST
            ]
        )
        // 700
        + 2
        + 1
    ) * min_txn_fee

    with pytest.raises(LogicError, match=err.SAFE_SIZE):
        verifiable_shuffle_client.opt_in_commit(
            delay=1,
            participants=participants,
            winners=winners + 1,
            transaction_parameters=TransactionParameters(
                signer=user_account.signer,
                sender=user_account.address,
                suggested_params=sp,
                foreign_apps=[opup_deployment.app.app_id],
            ),
        )

    verifiable_shuffle_client.opt_in_commit(
        delay=1,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer,
            sender=user_account.address,
            suggested_params=sp,
            foreign_apps=[opup_deployment.app.app_id],
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
    opup_deployment: DeployResponse,
    user_account: AddressAndSigner,
    test_scenario: Tuple[int, int],
) -> None:
    participants, winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = sp.fee = (
        (
            winners
            * verifiable_shuffle_client.app_client.template_values[
                cfg_vs.COMMIT_SINGLE_WINNER_OP_COST
            ]
        )
        // 700
        + 2
    ) * min_txn_fee

    verifiable_shuffle_client.opt_in_commit(
        delay=1,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer,
            sender=user_account.address,
            suggested_params=sp,
            foreign_apps=[opup_deployment.app.app_id],
        ),
    )

    verifiable_shuffle_client.clear_state(
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address
        )
    )
