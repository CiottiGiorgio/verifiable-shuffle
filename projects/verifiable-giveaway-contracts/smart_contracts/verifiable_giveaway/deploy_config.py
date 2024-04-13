from importlib.metadata import version
import logging
import os

import algokit_utils
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

logger = logging.getLogger(__name__)


# define deployment behaviour based on supplied app spec
def deploy(
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
    app_spec: algokit_utils.ApplicationSpecification,
    deployer: algokit_utils.Account,
) -> None:
    from smart_contracts.artifacts.verifiable_giveaway.client import (
        VerifiableGiveawayClient,
    )

    app_client = VerifiableGiveawayClient(
        algod_client,
        creator=deployer,
        indexer_client=indexer_client,
    )

    app_client.deploy(
        version=version("verifiable-giveaway"),
        on_schema_break=algokit_utils.OnSchemaBreak.ReplaceApp,
        on_update=algokit_utils.OnUpdate.UpdateApp,
        template_values={
            "RANDOMNESS_BEACON_ID": int(os.environ.get("RANDOMNESS_BEACON_ID")),
            "SAFETY_ROUND_GAP": int(os.environ.get("SAFETY_ROUND_GAP")),
        },
    )
