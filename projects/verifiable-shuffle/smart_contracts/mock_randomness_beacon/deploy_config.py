import hashlib
import logging

import algokit_utils
from algokit_utils import AppClientCompilationParams

logger = logging.getLogger(__name__)


# define deployment behaviour based on supplied app spec
def deploy() -> None:
    algorand = algokit_utils.AlgorandClient.from_environment()

    if algorand.client.is_localnet():
        import smart_contracts.mock_randomness_beacon.config as cfg
        from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
            MockRandomnessBeaconFactory,
            MustGetArgs,
        )

        deployer_ = algorand.account.from_environment("DEPLOYER")

        factory = algorand.client.get_typed_app_factory(
            MockRandomnessBeaconFactory, default_sender=deployer_.address
        )

        app_client, deployment_result = factory.deploy(
            on_update=algokit_utils.OnUpdate.AppendApp,
            on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
            compilation_params=AppClientCompilationParams(
                deploy_time_params={
                    cfg.OUTPUT: hashlib.sha3_256(b"NOT-SO-RANDOM-DATA").digest()
                },
            ),
        )
        round_arg = 0
        user_data = b""
        randomness = app_client.send.must_get(
            MustGetArgs(round=round_arg, user_data=user_data)
        )
        logger.info(
            f"Called must_get on {app_client.app_spec.name} ({app_client.app_id}) "
            f"with {round_arg = }, {user_data = !r}, received: {randomness.abi_return!r}"
        )
    else:
        logger.info("Not on LocalNet, nothing to do.")
