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
    from smart_contracts.artifacts.verifiable_shuffle_opup.verifiable_shuffle_opup_client import (
        APP_SPEC as OPUP_SPEC,
    )

    app_client = VerifiableShuffleClient(
        algod_client,
        creator=deployer,
        indexer_client=indexer_client,
    )

    @retry(stop=stop_after_attempt(10), wait=wait_fixed(2))  # type: ignore[misc]
    def get_creator_app_with_retry(contract_name: str) -> int:
        return get_creator_apps(indexer_client, deployer).apps[contract_name].app_id

    if is_localnet(algod_client):
        randomness_beacon = get_creator_app_with_retry(MOCK_RB_APP_SPEC.contract.name)
    else:
        randomness_beacon_from_env = os.environ.get(cfg.RANDOMNESS_BEACON)
        if randomness_beacon_from_env is None:
            raise Exception(
                f"{cfg.RANDOMNESS_BEACON} environment variable not set or not found in localnet"
            )
        randomness_beacon = int(randomness_beacon_from_env)

    verifiable_shuffle_opup = get_creator_app_with_retry(OPUP_SPEC.contract.name)
    safety_gap = os.environ.get(cfg.SAFETY_GAP)
    if safety_gap is None:
        raise Exception(f"{cfg.SAFETY_GAP} environment variable not set")

    app_client.deploy(
        on_update=algokit_utils.OnUpdate.UpdateApp,
        on_schema_break=algokit_utils.OnSchemaBreak.ReplaceApp,
        template_values={
            cfg.RANDOMNESS_BEACON: randomness_beacon,
            cfg.OPUP: verifiable_shuffle_opup,
            cfg.SAFETY_GAP: int(safety_gap),
        },
    )
    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = ((cfg.COMMIT_SINGLE_WINNER_OP_COST // 700) + 2) * min_txn_fee
    commitment = app_client.opt_in_commit(
        delay=int(safety_gap),
        participants=2,
        winners=1,
        transaction_parameters=TransactionParameters(
            suggested_params=sp, foreign_apps=[verifiable_shuffle_opup]
        ),
    )
    logger.info(
        f"Called opt_in_commit in {commitment.tx_id} on {app_spec.contract.name} ({app_client.app_id}) "
        f"with participants = 2, winners = 1, received: {commitment.return_value} "
    )

    # Even though delay=1, we still need to retry this transaction a couple of times because
    #  we could be waiting for the VRF off-the-chain service to upload the VRF result to the
    #  Randomness Beacon.
    @retry(stop=stop_after_attempt(21), wait=wait_fixed(3))  # type: ignore[misc]
    def reveal_with_retry() -> algokit_utils.ABITransactionResponse[Reveal]:
        sp = algod_client.suggested_params()
        sp.flat_fee = True
        sp.fee = ((cfg.REVEAL_SINGLE_WINNER_OP_COST // 700) + 3) * min_txn_fee

        return app_client.close_out_reveal(
            transaction_parameters=TransactionParameters(
                suggested_params=sp,
                foreign_apps=[randomness_beacon, verifiable_shuffle_opup],
            )
        )

    try:
        reveal = reveal_with_retry()
    except:
        app_client.clear_state()
        raise

    logger.info(
        f"Called close_out_reveal on {app_spec.contract.name} ({app_client.app_id}) "
        f"received: Commitment ID: {base64.b32encode(bytes(reveal.return_value.commitment_tx_id))!r} "
        f"and winners: {reveal.return_value.winners}"
    )
