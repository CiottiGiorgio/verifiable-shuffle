import base64
import hashlib

import algokit_utils
import algosdk.account
import pytest
from algokit_utils import (
    Account,
    DeployResponse,
    EnsureBalanceParameters,
    TransactionParameters,
    get_localnet_default_account,
)
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from smart_contracts.artifacts.mock_randomness_beacon.client import (
    MockRandomnessBeaconClient,
)
from smart_contracts.artifacts.verifiable_giveaway.client import (
    VerifiableGiveawayClient,
)


@pytest.fixture(scope="session")
def mock_randomness_beacon_deployment(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> tuple[DeployResponse, MockRandomnessBeaconClient]:
    config.configure(
        debug=True,
        trace_all=True,
    )

    client = MockRandomnessBeaconClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    deploy_response = client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.Fail,
        on_update=algokit_utils.OnUpdate.AppendApp,
        template_values={
            "VRF_OUTPUT": hashlib.sha3_256(b"NOT-SO-RANDOM-DATA").digest()
        },
    )
    return deploy_response, client


@pytest.fixture(scope="session")
def verifiable_giveaway_client(
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
    mock_randomness_beacon_deployment: tuple[
        DeployResponse, MockRandomnessBeaconClient
    ],
) -> VerifiableGiveawayClient:
    mbr_deployment, _ = mock_randomness_beacon_deployment

    client = VerifiableGiveawayClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
        template_values={
            "RANDOMNESS_BEACON_ID": mbr_deployment.app.app_id,
            "SAFETY_ROUND_GAP": 1,
        },
    )

    client.create_bare()
    return client


@pytest.fixture(scope="session")
def user_account(algod_client: AlgodClient) -> Account:
    sk, address = algosdk.account.generate_account()
    account = Account(private_key=sk, address=address)
    algokit_utils.ensure_funded(
        algod_client,
        EnsureBalanceParameters(
            account_to_fund=account, min_spending_balance_micro_algos=10_000_000
        ),
    )

    return account


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
        (80, 20, [34, 20, 9, 25, 22, 55, 14, 8, 7, 15, 2, 61, 24, 42, 75, 70, 36, 3, 43, 78]),
        (255, 16, [54, 160, 6, 130, 75, 4, 126, 207, 249, 103, 90, 134, 121, 86, 127, 165])
    ],
)
def test_shuffle(
    algod_client: AlgodClient,
    verifiable_giveaway_client: VerifiableGiveawayClient,
    mock_randomness_beacon_deployment: tuple[
        DeployResponse, MockRandomnessBeaconClient
    ],
    user_account: Account,
    test_scenario: tuple[int, int, list[int]],
) -> None:
    participants, winners, shuffled_winners = test_scenario
    last_round = algod_client.status()["last-round"]

    commit_result = verifiable_giveaway_client.opt_in_commit(
        block=last_round + 2,
        participants=participants,
        winners=winners,
        transaction_parameters=TransactionParameters(
            signer=user_account.signer, sender=user_account.address
        ),
    )

    assert commit_result.confirmed_round

    mrb_deployment, _ = mock_randomness_beacon_deployment
    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 2_000 + winners * 1_000 + 1_000

    reveal_result = verifiable_giveaway_client.close_out_reveal(
        transaction_parameters=TransactionParameters(
            signer=user_account.signer,
            sender=user_account.address,
            suggested_params=sp,
            foreign_apps=[mrb_deployment.app.app_id],
        )
    )
    revealed_commit_tx_id, revealed_winners = reveal_result.return_value

    assert (
        base64.b32encode(bytes(revealed_commit_tx_id)).decode().strip("=")
        == commit_result.tx_id
    )
    assert revealed_winners == shuffled_winners
