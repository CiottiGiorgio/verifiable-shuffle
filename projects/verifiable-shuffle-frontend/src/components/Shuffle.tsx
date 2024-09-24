import * as algokit from '@algorandfoundation/algokit-utils'
import { useWallet } from '@txnlab/use-wallet'
import { useSnackbar } from 'notistack'
import { retry } from 'ts-retry'
import { useState } from 'react'
import { getAlgodConfigFromViteEnvironment, getIndexerConfigFromViteEnvironment } from '../utils/network/getAlgoClientConfigs'
import { VerifiableShuffleClient } from '../contracts/VerifiableShuffle'
import { getShuffleDeploymentConfigFromViteEnvironment } from '../utils/getShuffleDeploymentConfig'
import { makeEmptyTransactionSigner } from 'algosdk'
import { lookupAccountByAddress } from '@algorandfoundation/algokit-utils'

interface ShuffleInterface {
  openModal: boolean
  setModalState: (value: boolean) => void
}

const Shuffle = ({ openModal, setModalState }: ShuffleInterface) => {
  const [loading, setLoading] = useState<boolean>(false)
  const [participants, setParticipants] = useState<number>()
  const [winners, setWinners] = useState<number>()
  const [selectedWinners, setSelectedWinners] = useState<number[]>()

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
      setSelectedWinners([])
      const {
        returns: [knownRandomnessBeacon, knownOpUp],
      } = await verifiableShuffleClientWithEmptySigner
        .compose()
        .getTemplatedRandomnessBeaconId({})
        .getTemplatedOpupId({})
        .simulate({ allowEmptySignatures: true })

      const { appId } = await verifiableShuffleClient.appClient.getAppReference()
      const localState = await lookupAccountByAddress(activeAddress, indexerClient)
      let commitContingentOptIn
      if (localState.account['apps-local-state']?.find((localState) => localState.id == appId) !== undefined) {
        commitContingentOptIn = verifiableShuffleClient
      } else {
        commitContingentOptIn = verifiableShuffleClient.optIn
      }
      await commitContingentOptIn.commit(
        { participants: Number(participants), winners: Number(winners), delay: 1 },
        {
          apps: [Number(knownOpUp)],
          sendParams: { fee: algokit.algos(0.001 * (winners! + 2)) },
        },
      )

      const revealComposer = verifiableShuffleClient.compose().reveal(
        {},
        {
          apps: [Number(knownRandomnessBeacon), Number(knownOpUp)],
          sendParams: { fee: algokit.algos(0.001 * (winners! + 3)) },
        },
      )
      const {
        returns: [revealResult],
      } = await retry(async () => await revealComposer.execute(), {
        delay: 10_000,
        maxTry: 21,
      })
      enqueueSnackbar(`Selected winners: ${revealResult.winners.join(', ')}`, { variant: 'success' })
      setParticipants(undefined)
      setWinners(undefined)
      setSelectedWinners(revealResult.winners)
    } catch (e) {
      enqueueSnackbar('Failed to send transaction', { variant: 'error' })
    }

    setLoading(false)
  }

  return (
    <dialog id="transact_modal" className={`modal ${openModal ? 'modal-open' : ''} bg-slate-200`}>
      <form method="dialog" className="modal-box">
        <h3 className="font-bold text-lg">Send Shuffle Application Call</h3>
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
        <br />
        <input
          type="text"
          data-test-id="selected-winners"
          placeholder="Selected winners"
          className="input input-bordered w-full disabled"
          value={selectedWinners?.join(', ') || ''}
          readOnly={true}
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
