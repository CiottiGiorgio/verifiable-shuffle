import hashlib
import logging

import algokit_utils
from algokit_utils import is_localnet
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
    if is_localnet(algod_client):
        import smart_contracts.mock_randomness_beacon.config as cfg
        from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
            MockRandomnessBeaconClient,
        )

        app_client = MockRandomnessBeaconClient(
            algod_client,
            creator=deployer,
            indexer_client=indexer_client,
        )
        app_client.deploy(
            on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
            on_update=algokit_utils.OnUpdate.AppendApp,
            template_values={
                cfg.OUTPUT: hashlib.sha3_256(b"NOT-SO-RANDOM-DATA").digest()
            },
        )
        round_arg = 0
        user_data = b""
        randomness = app_client.must_get(round=round_arg, user_data=user_data)
        logger.info(
            f"Called must_get on {app_spec.contract.name} ({app_client.app_id}) "
            f"with {round_arg = }, {user_data = !r}, received: {randomness.return_value!r}"
        )
    else:
        logger.info("Not on LocalNet. Nothing to do.")
