import base64
import hashlib
import json

import algokit_utils
import pytest
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AppClientCompilationParams,
    AppFactoryDeployResult,
    CommonAppCallParams,
    LogicError,
    SigningAccount, AppSourceMaps,
)
from algosdk.constants import min_txn_fee

import smart_contracts.mock_randomness_beacon.config as cfg_rb
import smart_contracts.verifiable_shuffle.config as cfg_vs
import smart_contracts.verifiable_shuffle.errors as err
from smart_contracts.artifacts.mock_randomness_beacon.mock_randomness_beacon_client import (
    MockRandomnessBeaconFactory,
)
from smart_contracts.artifacts.verifiable_shuffle.verifiable_shuffle_client import (
    CommitArgs,
    VerifiableShuffleClient,
    VerifiableShuffleFactory,
)
from smart_contracts.artifacts.verifiable_shuffle_opup.verifiable_shuffle_opup_client import (
    VerifiableShuffleOpupFactory,
)


@pytest.fixture(scope="session")
def deployer(algorand_client: AlgorandClient) -> SigningAccount:
    account = algorand_client.account.from_environment("DEPLOYER")
    algorand_client.account.ensure_funded_from_environment(
        account_to_fund=account.address, min_spending_balance=AlgoAmount.from_algo(10)
    )
    return account


@pytest.fixture(scope="session")
def user_account(algorand_client: AlgorandClient) -> SigningAccount:
    account = algorand_client.account.random()
    algorand_client.account.ensure_funded_from_environment(
        account_to_fund=account.address, min_spending_balance=AlgoAmount.from_algo(10)
    )
    return account


@pytest.fixture(scope="session")
def mock_randomness_beacon_deployment(
    algorand_client: AlgorandClient, deployer: SigningAccount
) -> AppFactoryDeployResult:
    factory = algorand_client.client.get_typed_app_factory(
        MockRandomnessBeaconFactory, default_sender=deployer.address
    )

    _, deployment = factory.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.Fail,
        on_update=algokit_utils.OnUpdate.AppendApp,
        compilation_params=AppClientCompilationParams(
            deploy_time_params={
                cfg_rb.OUTPUT: hashlib.sha3_256(b"NOT-SO-RANDOM-DATA").digest()
            },
        ),
    )
    return deployment


@pytest.fixture(scope="session")
def opup_deployment(
    algorand_client: AlgorandClient, deployer: SigningAccount
) -> AppFactoryDeployResult:
    factory = algorand_client.client.get_typed_app_factory(
        VerifiableShuffleOpupFactory, default_sender=deployer.address
    )

    _, deployment = factory.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.Fail,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )
    return deployment


@pytest.fixture(scope="session")
def verifiable_shuffle_client(
    algorand_client: AlgorandClient,
    deployer: SigningAccount,
    user_account: SigningAccount,
    mock_randomness_beacon_deployment: AppFactoryDeployResult,
    opup_deployment: AppFactoryDeployResult,
) -> VerifiableShuffleClient:
    factory = algorand_client.client.get_typed_app_factory(
        VerifiableShuffleFactory, default_sender=deployer.address
    )

    client, _ = factory.send.create.bare(
        compilation_params=AppClientCompilationParams(
            deploy_time_params={
                cfg_vs.RANDOMNESS_BEACON: mock_randomness_beacon_deployment.app.app_id,
                cfg_vs.OPUP: opup_deployment.app.app_id,
                cfg_vs.SAFETY_GAP: 1,
            },
        ),
    )
    return client.clone(
        default_sender=user_account.address, default_signer=user_account.signer
    )


# These test cases are not derived from a reference implementation but rather just used to detect instability
#  in the algorithm.
@pytest.mark.parametrize(
    "test_scenario",
    [
        (2, 1, [1]),
        (2, 2, [1, 0]),
        (5, 2, [3, 1]),
        (10, 3, [3, 0, 4]),
        (10, 9, [3, 0, 4, 1, 5, 9, 2, 6, 7]),
        (10, 10, [3, 0, 4, 1, 5, 9, 2, 6, 7, 8]),
        (80, 1, [33]),
        (80, 5, [33, 19, 8, 24, 21]),
        (
            80,
            20,
            [33, 19, 8, 24, 21, 54, 13, 7, 6, 14, 1, 60, 23, 41, 74, 69, 35, 2, 42, 77],
        ),
        (
            2**8 - 1,
            16,
            [53, 159, 5, 129, 74, 3, 125, 206, 248, 102, 89, 133, 120, 85, 126, 164],
        ),
        (2**16 - 1, 8, [65078, 39277, 24201, 18093, 24360, 54079, 9977, 5054]),
        (2**32 - 2, 4, [146095707, 3969517344, 3683389088, 196699749]),
    ],
)
def test_sequence(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    mock_randomness_beacon_deployment: AppFactoryDeployResult,
    opup_deployment: AppFactoryDeployResult,
    test_scenario: tuple[int, int, list[int]],
) -> None:
    participants, winners, shuffled_winners = test_scenario

    commit_result = verifiable_shuffle_client.send.opt_in.commit(
        CommitArgs(
            delay=1,
            participants=participants,
            winners=winners,
        ),
        params=CommonAppCallParams(
            app_references=[opup_deployment.app.app_id],
            extra_fee=AlgoAmount.from_micro_algo(
                ((winners * cfg_vs.COMMIT_SINGLE_WINNER_OP_COST) // 700 + 1)
                * min_txn_fee
            ),
        ),
    )
    assert commit_result.confirmation["confirmed-round"]

    reveal_result = verifiable_shuffle_client.send.close_out.reveal(
        params=CommonAppCallParams(
            app_references=[
                mock_randomness_beacon_deployment.app.app_id,
                opup_deployment.app.app_id,
            ],
            extra_fee=AlgoAmount.from_micro_algo(
                ((winners * cfg_vs.REVEAL_SINGLE_WINNER_OP_COST) // 700 + 2)
                * min_txn_fee
            ),
        )
    )
    reveal_outcome = reveal_result.abi_return

    assert (
        base64.b32encode(bytes(reveal_outcome.commitment_tx_id)).decode().strip("=")
        == commit_result.tx_ids[0]
    )
    assert reveal_outcome.winners == shuffled_winners


@pytest.mark.parametrize(
    "test_scenario",
    [
        (2**32 - 1, 4),
        (2**16 - 1, 8),
        (2**8 - 1, 16),
        (80, 20),
        (47, 25),
        (35, 30),
    ],
)
def test_safety_bounds(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    opup_deployment: AppFactoryDeployResult,
    test_scenario: tuple[int, int],
) -> None:
    participants, winners = test_scenario

    # FIXME: Re-instate the matching of the error message.
    # with pytest.raises(LogicError, match=err.SAFE_SIZE):
    with pytest.raises(LogicError):
        verifiable_shuffle_client.send.opt_in.commit(
            CommitArgs(
                delay=1,
                participants=participants,
                winners=winners + 1,
            ),
            params=CommonAppCallParams(
                app_references=[opup_deployment.app.app_id],
                extra_fee=AlgoAmount.from_micro_algo(
                    ((winners * cfg_vs.COMMIT_SINGLE_WINNER_OP_COST) // 700 + 2 + 1)
                    * min_txn_fee
                ),
            ),
        )

    verifiable_shuffle_client.send.opt_in.commit(
        CommitArgs(
            delay=1,
            participants=participants,
            winners=winners,
        ),
        params=CommonAppCallParams(
            app_references=[opup_deployment.app.app_id],
            extra_fee=AlgoAmount.from_micro_algo(
                ((winners * cfg_vs.COMMIT_SINGLE_WINNER_OP_COST) // 700 + 2)
                * min_txn_fee
            ),
        ),
    )

    verifiable_shuffle_client.send.clear_state()


# We can't test that this will fail for winners+1 because that would mean we have more winners than
#  participants.
@pytest.mark.parametrize(
    "test_scenario",
    [
        (34, 34),
    ],
)
def test_special_case(
    algorand_client: AlgorandClient,
    verifiable_shuffle_client: VerifiableShuffleClient,
    opup_deployment: AppFactoryDeployResult,
    user_account: SigningAccount,
    test_scenario: tuple[int, int],
) -> None:
    participants, winners = test_scenario

    verifiable_shuffle_client.send.opt_in.commit(
        CommitArgs(
            delay=1,
            participants=participants,
            winners=winners,
        ),
        params=CommonAppCallParams(
            app_references=[opup_deployment.app.app_id],
            extra_fee=AlgoAmount.from_micro_algo(
                ((winners * cfg_vs.COMMIT_SINGLE_WINNER_OP_COST) // 700 + 2)
                * min_txn_fee
            ),
        ),
    )

    verifiable_shuffle_client.send.clear_state()
