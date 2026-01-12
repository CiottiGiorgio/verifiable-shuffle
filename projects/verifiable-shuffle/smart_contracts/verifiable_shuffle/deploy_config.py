import base64
import logging
import os

import algokit_utils
from algokit_utils import (
    AlgoAmount,
    AppClientBareCallParams,
    AppClientCompilationParams,
    CommonAppCallParams,
    SendAppTransactionResult,
)
from algosdk.constants import min_txn_fee
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


# define deployment behaviour based on supplied app spec
def deploy() -> None:
    from smart_contracts.artifacts.verifiable_shuffle.verifiable_shuffle_client import (
        CommitArgs,
        Reveal,
        VerifiableShuffleFactory,
    )

    import smart_contracts.verifiable_shuffle.config as cfg
    from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
        MockRandomnessBeaconClient,
        MockRandomnessBeaconFactory,
    )
    from smart_contracts.artifacts.verifiable_shuffle_opup.verifiable_shuffle_opup_client import (
        VerifiableShuffleOpupClient,
        VerifiableShuffleOpupFactory,
    )

    algorand = algokit_utils.AlgorandClient.from_environment()
    dispenser_ = algorand.account.from_environment("DISPENSER")
    deployer_ = algorand.account.from_environment("DEPLOYER")
    user_ = algorand.account.from_environment("USER")

    opup_factory = algorand.client.get_typed_app_factory(
        VerifiableShuffleOpupFactory, default_sender=deployer_.address
    )

    @retry(stop=stop_after_attempt(10), wait=wait_fixed(2))  # type: ignore[misc]
    def get_opup_with_retry() -> VerifiableShuffleOpupClient:
        return opup_factory.get_app_client_by_creator_and_name(
            deployer_.address, opup_factory.app_spec.name
        )

    opup = get_opup_with_retry().app_id

    if algorand.client.is_localnet():
        mock_randomness_beacon_factory = algorand.client.get_typed_app_factory(
            MockRandomnessBeaconFactory, default_sender=deployer_.address
        )

        @retry(stop=stop_after_attempt(10), wait=wait_fixed(2))  # type: ignore[misc]
        def get_mock_randomness_beacon_with_retry() -> MockRandomnessBeaconClient:
            return mock_randomness_beacon_factory.get_app_client_by_creator_and_name(
                deployer_.address, mock_randomness_beacon_factory.app_spec.name
            )

        randomness_beacon = get_mock_randomness_beacon_with_retry().app_id
    else:
        randomness_beacon_from_env = os.environ.get(cfg.RANDOMNESS_BEACON)
        if randomness_beacon_from_env is None:
            raise Exception(
                f"{cfg.RANDOMNESS_BEACON} environment variable not set or found"
            )
        randomness_beacon = int(randomness_beacon_from_env)

    safety_gap = os.environ.get(cfg.SAFETY_GAP)
    if safety_gap is None:
        raise Exception(f"{cfg.SAFETY_GAP} environment variable not set")

    verifiable_shuffle_factory = algorand.client.get_typed_app_factory(
        VerifiableShuffleFactory, default_sender=deployer_.address
    )
    verifiable_shuffle_client, _ = verifiable_shuffle_factory.deploy(
        on_update=algokit_utils.OnUpdate.UpdateApp,
        on_schema_break=algokit_utils.OnSchemaBreak.ReplaceApp,
        compilation_params=AppClientCompilationParams(
            deploy_time_params={
                cfg.RANDOMNESS_BEACON: randomness_beacon,
                cfg.OPUP: opup,
                cfg.SAFETY_GAP: int(safety_gap),
            },
        ),
    )

    algorand.account.ensure_funded(
        account_to_fund=user_,
        dispenser_account=dispenser_,
        min_spending_balance=AlgoAmount(algo=1),
        min_funding_increment=AlgoAmount(algo=1),
    )

    # Just in case something went wrong in previous deployment runs, and we didn't actually clear the state,
    #  let's check if we are already opted in.
    try:
        verifiable_shuffle_client.state.local_state(user_.address).get_all()
        logger.info(
            "Cleaning up after a previous failed deployment. Called clear_state."
        )
        verifiable_shuffle_client.send.clear_state(
            params=AppClientBareCallParams(sender=user_.address, signer=user_.signer)
        )
    except Exception:
        pass

    commitment = verifiable_shuffle_client.send.opt_in.commit(
        CommitArgs(
            delay=int(safety_gap),
            participants=2,
            winners=1,
        ),
        params=CommonAppCallParams(
            app_references=[opup],
            extra_fee=AlgoAmount(
                micro_algo=((cfg.COMMIT_SINGLE_WINNER_OP_COST // 700) + 1) * min_txn_fee
            ),
            sender=user_.address,
            signer=user_.signer,
        ),
    )
    logger.info(
        f"Called opt_in_commit in {commitment.tx_id} on {verifiable_shuffle_client.app_spec.name} "
        f"({verifiable_shuffle_client.app_id}) "
        f"with participants = 2, winners = 1, received: {commitment.abi_return} "
    )

    # Even though delay=1, we still need to retry this transaction a couple of times because
    #  we could be waiting for the VRF off-the-chain service to upload the VRF result to the
    #  Randomness Beacon.
    @retry(stop=stop_after_attempt(21), wait=wait_fixed(3))  # type: ignore[misc]
    def reveal_with_retry() -> SendAppTransactionResult[Reveal]:
        return verifiable_shuffle_client.send.close_out.reveal(
            params=CommonAppCallParams(
                app_references=[randomness_beacon, opup],
                extra_fee=AlgoAmount(
                    micro_algo=((cfg.REVEAL_SINGLE_WINNER_OP_COST // 700) + 3)
                    * min_txn_fee
                ),
                sender=user_.address,
                signer=user_.signer,
            ),
        )

    try:
        reveal = reveal_with_retry()
    except:
        verifiable_shuffle_client.send.clear_state(
            params=AppClientBareCallParams(sender=user_.address, signer=user_.signer)
        )
        logger.info(
            f"Called clear_state on {verifiable_shuffle_client.app_spec.name} "
            f"({verifiable_shuffle_client.app_id}) "
        )
        raise

    if not reveal.abi_return:
        raise ValueError("Expected reveal to return an ABI value.")

    logger.info(
        f"Called close_out_reveal on {verifiable_shuffle_client.app_spec.name} "
        f"({verifiable_shuffle_client.app_id}) "
        f"received: Commitment ID: {base64.b32encode(bytes(reveal.abi_return.commitment_tx_id))!r} "
        f"and winners: {reveal.abi_return.winners}"
    )
