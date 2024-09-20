import * as algokit from '@algorandfoundation/algokit-utils'
import { useWallet } from '@txnlab/use-wallet'
import { useSnackbar } from 'notistack'
import { retry } from 'ts-retry'
import { useState } from 'react'
import { getAlgodConfigFromViteEnvironment, getIndexerConfigFromViteEnvironment } from '../utils/network/getAlgoClientConfigs'
import { VerifiableShuffleClient } from '../contracts/VerifiableShuffle'
import { getShuffleDeploymentConfigFromViteEnvironment } from '../utils/getShuffleDeploymentConfig'
import { makeEmptyTransactionSigner } from 'algosdk'

interface ShuffleInterface {
  openModal: boolean
  setModalState: (value: boolean) => void
}

const Shuffle = ({ openModal, setModalState }: ShuffleInterface) => {
  const [loading, setLoading] = useState<boolean>(false)
  const [participants, setParticipants] = useState<number>()
  const [winners, setWinners] = useState<number>()

  const algodConfig = getAlgodConfigFromViteEnvironment()
  const algodClient = algokit.getAlgoClient({
    server: algodConfig.server,
    port: algodConfig.port,
    token: algodConfig.token,
  })
  const indexerConfig = getIndexerConfigFromViteEnvironment()
  const indexerClient = algokit.getAlgoIndexerClient({
    server: indexerConfig.server,
    port: indexerConfig.port,
    token: indexerConfig.token,
  })
  const { creatorAddress } = getShuffleDeploymentConfigFromViteEnvironment()

  const { enqueueSnackbar } = useSnackbar()

  const { signer, activeAddress } = useWallet()

  const handleShuffle = async () => {
    setLoading(true)

    if (!signer || !activeAddress) {
      enqueueSnackbar('Please connect wallet first', { variant: 'warning' })
      return
    }

    const verifiableShuffleClient = new VerifiableShuffleClient(
      {
        resolveBy: 'creatorAndName',
        creatorAddress: creatorAddress,
        findExistingUsing: indexerClient,
        sender: { addr: activeAddress, signer },
      },
      algodClient,
    )
    const verifiableShuffleClientWithEmptySigner = new VerifiableShuffleClient(
      {
        resolveBy: 'creatorAndName',
        creatorAddress: creatorAddress,
        findExistingUsing: indexerClient,
        sender: { addr: activeAddress, signer: makeEmptyTransactionSigner() },
      },
      algodClient,
    )

    try {
      enqueueSnackbar('Sending transaction...', { variant: 'info' })
      const {
        returns: [knownRandomnessBeacon],
      } = await verifiableShuffleClientWithEmptySigner.compose().getTemplatedRandomnessBeaconId({}).simulate({ allowEmptySignatures: true })
      const {
        returns: [knownOpUp],
      } = await verifiableShuffleClientWithEmptySigner.compose().getTemplatedOpupId({}).simulate({ allowEmptySignatures: true })

      await verifiableShuffleClient.commit(
        { participants: Number(participants), winners: Number(winners), delay: 1 },
        {
          apps: [Number(knownOpUp)],
          sendParams: { fee: algokit.algos(0.001 * (winners! + 2)) },
        },
      )

      const { return: revealResult } = await retry(
        async () =>
          verifiableShuffleClient.reveal(
            {},
            {
              apps: [Number(knownRandomnessBeacon), Number(knownOpUp)],
              sendParams: { fee: algokit.algos(0.001 * (winners! + 3)) },
            },
          ),
        {
          delay: 10_000,
          maxTry: 21,
        },
      )
      enqueueSnackbar(`Transaction sent: ${revealResult!.winners}`, { variant: 'success' })
      setParticipants(undefined)
      setWinners(undefined)
    } catch (e) {
      enqueueSnackbar('Failed to send transaction', { variant: 'error' })
    }

    setLoading(false)
  }

  return (
    <dialog id="transact_modal" className={`modal ${openModal ? 'modal-open' : ''} bg-slate-200`}>
      <form method="dialog" className="modal-box">
        <h3 className="font-bold text-lg">Send payment transaction</h3>
        <br />
        <input
          type="number"
          data-test-id="participants"
          placeholder="Provide the number of participants"
          className="input input-bordered w-full"
          value={participants || ''}
          onChange={(e) => {
            setParticipants(Number(e.target.value))
          }}
        />
        <input
          type="number"
          data-test-id="winners"
          placeholder="Provide the number of winners"
          className="input input-bordered w-full"
          value={winners || ''}
          onChange={(e) => {
            setWinners(Number(e.target.value))
          }}
        />
        <div className="modal-action ">
          <button className="btn" onClick={() => setModalState(!openModal)}>
            Close
          </button>
          <button data-test-id="shuffle" className={`btn lo`} onClick={handleShuffle}>
            {loading ? <span className="loading loading-spinner" /> : 'Shuffle'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

export default Shuffle
