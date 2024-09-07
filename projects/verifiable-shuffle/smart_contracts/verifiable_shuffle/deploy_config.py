import base64
import logging
import os

import algokit_utils
from algokit_utils import TransactionParameters, is_localnet
from algokit_utils.deploy import get_creator_apps
from algosdk.constants import min_txn_fee
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


# define deployment behaviour based on supplied app spec
def deploy(
    algod_client: AlgodClient,
    indexer_client: IndexerClient,
    app_spec: algokit_utils.ApplicationSpecification,
    deployer: algokit_utils.Account,
) -> None:
    import smart_contracts.verifiable_shuffle.config as cfg
    from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
        APP_SPEC as MOCK_RB_APP_SPEC,
    )
    from smart_contracts.artifacts.verifiable_shuffle.verifiable_shuffle_client import (
        Reveal,
        VerifiableShuffleClient,
    )

    app_client = VerifiableShuffleClient(
        algod_client,
        creator=deployer,
        indexer_client=indexer_client,
    )

    if is_localnet(algod_client):

        @retry(stop=stop_after_attempt(10), wait=wait_fixed(2))  # type: ignore[misc]
        def get_mock_randomness_beacon_app_id() -> int:
            return (
                get_creator_apps(indexer_client, deployer)
                .apps[MOCK_RB_APP_SPEC.contract.name]
                .app_id
            )

        randomness_beacon = get_mock_randomness_beacon_app_id()
    else:
        env_randomness_beacon = os.environ.get(cfg.RANDOMNESS_BEACON)
        if env_randomness_beacon is None:
            raise Exception(
                f"{cfg.RANDOMNESS_BEACON} environment variable not set or not found in localnet"
            )
        randomness_beacon = int(env_randomness_beacon)

    safety_gap = os.environ.get(cfg.SAFETY_GAP)
    if safety_gap is None:
        raise Exception(f"{cfg.SAFETY_GAP} environment variable not set")

    app_client.deploy(
        on_update=algokit_utils.OnUpdate.UpdateApp,
        on_schema_break=algokit_utils.OnSchemaBreak.ReplaceApp,
        template_values={
            cfg.RANDOMNESS_BEACON: randomness_beacon,
            cfg.SAFETY_GAP: int(safety_gap),
            "COMMIT_OPUP_SCALING_COST_CONSTANT": 700,
            "REVEAL_OPUP_SCALING_COST_CONSTANT": 600,
        },
    )
    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 2 * min_txn_fee
    commitment = app_client.opt_in_commit(
        delay=int(safety_gap),
        participants=2,
        winners=1,
        transaction_parameters=TransactionParameters(suggested_params=sp),
    )
    logger.info(
        f"Called opt_in_commit in {commitment.tx_id} on {app_spec.contract.name} ({app_client.app_id}) "
        f"with participants = 2, winners = 1, received: {commitment.return_value} "
    )

    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 2 * min_txn_fee

    @retry(stop=stop_after_attempt(21), wait=wait_fixed(3))  # type: ignore[misc]
    def reveal_with_retry() -> algokit_utils.ABITransactionResponse[Reveal]:
        return app_client.close_out_reveal(
            transaction_parameters=TransactionParameters(
                suggested_params=sp, foreign_apps=[randomness_beacon]
            )
        )

    reveal = reveal_with_retry()
    logger.info(
        f"Called close_out_reveal on {app_spec.contract.name} ({app_client.app_id}) "
        f"received: Commitment ID: {base64.b32encode(bytes(reveal.return_value.commitment_tx_id))!r} "
        f"and winners: {reveal.return_value.winners}"
    )
