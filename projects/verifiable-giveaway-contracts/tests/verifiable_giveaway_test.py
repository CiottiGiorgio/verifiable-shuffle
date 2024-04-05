import algokit_utils
import pytest
from algokit_utils import get_localnet_default_account
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from smart_contracts.artifacts.verifiable_giveaway.client import VerifiableGiveawayClient


@pytest.fixture(scope="session")
def verifiable_giveaway_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> VerifiableGiveawayClient:
    config.configure(
        debug=True,
        # trace_all=True,
    )

    client = VerifiableGiveawayClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )
    return client


def test_says_hello(verifiable_giveaway_client: VerifiableGiveawayClient) -> None:
    result = verifiable_giveaway_client.hello(name="World")

    assert result.return_value == "Hello, World"


def test_simulate_says_hello_with_correct_budget_consumed(
    verifiable_giveaway_client: VerifiableGiveawayClient, algod_client: AlgodClient
) -> None:
    result = (
        verifiable_giveaway_client.compose().hello(name="World").hello(name="Jane").simulate()
    )

    assert result.abi_results[0].return_value == "Hello, World"
    assert result.abi_results[1].return_value == "Hello, Jane"
    assert result.simulate_response["txn-groups"][0]["app-budget-consumed"] < 100
