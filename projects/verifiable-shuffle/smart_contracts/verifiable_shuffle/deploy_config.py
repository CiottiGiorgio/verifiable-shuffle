import logging
import os
from importlib.metadata import version

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
    from smart_contracts.artifacts.verifiable_shuffle.verifiable_shuffle_client import (
        VerifiableShuffleClient,
    )

    app_client = VerifiableShuffleClient(
        algod_client,
        creator=deployer,
        indexer_client=indexer_client,
    )

    randomness_beacon_id = os.environ.get("RANDOMNESS_BEACON_ID")
    safety_round_gap = os.environ.get("SAFETY_ROUND_GAP")
    if not randomness_beacon_id or not safety_round_gap:
        raise ValueError

    app_client.deploy(
        version=version("verifiable-shuffle"),
        on_update=algokit_utils.OnUpdate.UpdateApp,
        on_schema_break=algokit_utils.OnSchemaBreak.ReplaceApp,
        template_values={
            "RANDOMNESS_BEACON_ID": int(randomness_beacon_id),
            "SAFETY_ROUND_GAP": int(safety_round_gap),
        },
    )
