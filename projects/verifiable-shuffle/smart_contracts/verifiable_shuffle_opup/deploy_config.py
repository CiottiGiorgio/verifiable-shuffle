import logging

import algokit_utils
from algokit_utils import (
    EnsureBalanceParameters,
    TransactionParameters,
    ensure_funded,
    get_account,
)
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
    from smart_contracts.artifacts.verifiable_shuffle_opup.verifiable_shuffle_opup_client import (
        VerifiableShuffleOpupClient,
    )

    app_client = VerifiableShuffleOpupClient(
        algod_client,
        creator=deployer,
        indexer_client=indexer_client,
    )
    app_client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )

    user = get_account(algod_client, "USER", fund_with_algos=0)
    ensure_funded(
        algod_client,
        EnsureBalanceParameters(
            account_to_fund=user,
            min_spending_balance_micro_algos=1_000_000,
            min_funding_increment_micro_algos=1_000_000,
        ),
    )

    app_client.no_op(
        transaction_parameters=TransactionParameters(
            signer=user.signer, sender=user.address
        )
    )
    logger.info(f"Called bare NoOp on {app_spec.contract.name} ({app_client.app_id}) ")
