import base64
import hashlib

import algokit_utils
import pytest
from algokit_utils import (
    DeployResponse,
    EnsureBalanceParameters,
    TransactionParameters,
    get_localnet_default_account,
)
from algokit_utils.beta.account_manager import AddressAndSigner
from algokit_utils.beta.algorand_client import AlgorandClient
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
    MockRandomnessBeaconClient,
)
from smart_contracts.artifacts.verifiable_giveaway.verifiable_giveaway_client import (
    VerifiableGiveawayClient,
)


@pytest.fixture(scope="session")
def mock_randomness_beacon_deployment(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> DeployResponse:
    config.configure(
        debug=True,
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
            "VRF_OUTPUT": hashlib.sha3_256(b"NOT-SO-RANDOM-DATA").digest()
        },
    )


@pytest.fixture(scope="session")
def verifiable_giveaway_client(
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
    mock_randomness_beacon_deployment: DeployResponse,
) -> VerifiableGiveawayClient:
    client = VerifiableGiveawayClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
        template_values={
            "RANDOMNESS_BEACON_ID": mock_randomness_beacon_deployment.app.app_id,
            "SAFETY_ROUND_GAP": 1,
            "LOGARITHM_FRACTIONAL_PRECISION": 10,
            "OPUP_CALLS_SAFETY_CHECK": 10,
            "OPUP_CALLS_DICT_INIT": 5,
            "OPUP_CALLS_KNUTH_SHUFFLE": 15,
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
            255,
            16,
            [54, 160, 6, 130, 75, 4, 126, 207, 249, 103, 90, 134, 121, 86, 127, 165],
        ),
    ],
)
def test_shuffle(
    algorand_client: AlgorandClient,
    verifiable_giveaway_client: VerifiableGiveawayClient,
    mock_randomness_beacon_deployment: DeployResponse,
    user_account: AddressAndSigner,
    test_scenario: tuple[int, int, list[int]],
) -> None:
    participants, winners, shuffled_winners = test_scenario

    sp = algorand_client.client.algod.suggested_params()
    sp.flat_fee = True
    sp.fee = 11_000

    commit_result = verifiable_giveaway_client.opt_in_commit(
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
    sp.fee = 21_000

    reveal_result = verifiable_giveaway_client.close_out_reveal(
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
