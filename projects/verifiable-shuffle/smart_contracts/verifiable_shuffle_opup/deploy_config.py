import logging

import algokit_utils
from algokit_utils import (
    AlgoAmount,
    AppClientBareCallParams,
)

logger = logging.getLogger(__name__)


# define deployment behaviour based on supplied app spec
def deploy() -> None:
    from smart_contracts.artifacts.verifiable_shuffle_opup.verifiable_shuffle_opup_client import (
        VerifiableShuffleOpupFactory,
    )

    algorand = algokit_utils.AlgorandClient.from_environment()
    dispenser_ = algorand.account.from_environment("DISPENSER")
    deployer_ = algorand.account.from_environment("DEPLOYER")
    user_ = algorand.account.from_environment("USER")

    factory = algorand.client.get_typed_app_factory(
        VerifiableShuffleOpupFactory, default_sender=deployer_.address
    )

    app_client, deployment_result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    algorand.account.ensure_funded(
        account_to_fund=user_,
        dispenser_account=dispenser_,
        min_spending_balance=AlgoAmount(algo=1),
        min_funding_increment=AlgoAmount(algo=1),
    )

    app_client.new_group().add_transaction(
        app_client.app_client.create_transaction.bare.call(
            params=AppClientBareCallParams(sender=user_.address, signer=user_.signer)
        )
    ).send()
    logger.info(
        f"Called bare NoOp on {app_client.app_spec.name} ({app_client.app_id}) "
    )
