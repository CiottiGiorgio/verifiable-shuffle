import * as algokit from '@algorandfoundation/algokit-utils'
import { TransactionSignerAccount } from '@algorandfoundation/algokit-utils/types/account'
import { useWallet } from '@txnlab/use-wallet'
import { useSnackbar } from 'notistack'
import { useState } from 'react'
import { AppDetails } from '@algorandfoundation/algokit-utils/types/app-client'
import { AccountLookupResult, AppLocalState } from '@algorandfoundation/algokit-utils/types/indexer'
import { VerifiableGiveawayClient } from '../contracts/VerifiableGiveaway'
import { getAlgodConfigFromViteEnvironment, getIndexerConfigFromViteEnvironment } from '../utils/network/getAlgoClientConfigs'
import { useQuery } from '@tanstack/react-query'
import base32 from 'hi-base32'
import { decodeUint64 } from 'algosdk'
import { microAlgos } from '@algorandfoundation/algokit-utils'

interface AppCallsInterface {
  openModal: boolean
  setModalState: (value: boolean) => void
}

const AppCalls = ({ openModal, setModalState }: AppCallsInterface) => {
  const [loading, setLoading] = useState<boolean>(false)
  const [commitmentDelay, setCommitmentDelay] = useState<string>('')
  const [commitmentParticipants, setCommitmentParticipants] = useState<string>('')
  const [commitmentWinners, setCommitmentWinners] = useState<string>('')
  const [newCommitmentID, setNewCommitmentID] = useState<string>('')
  const [newRevealID, setNewRevealID] = useState<string>('')
  const [revealedCommitmentID, setRevealedCommitmentID] = useState<string>('')
  const [revealedWinners, setRevealedWinners] = useState<string>('')

  const algodConfig = getAlgodConfigFromViteEnvironment()
  const algodClient = algokit.getAlgoClient({
    server: algodConfig.server,
    port: algodConfig.port,
    token: algodConfig.token,
  })
  const indexerConfig = getIndexerConfigFromViteEnvironment()
  const indexer = algokit.getAlgoIndexerClient({
    server: indexerConfig.server,
    port: indexerConfig.port,
    token: indexerConfig.token,
  })

  const { enqueueSnackbar } = useSnackbar()
  const { signer, activeAddress } = useWallet()

  const appDetails = {
    resolveBy: 'creatorAndName',
    sender: { signer, addr: activeAddress } as TransactionSignerAccount,
    creatorAddress: import.meta.env.VITE_DEPLOYER_ADDRESS,
    name: 'VerifiableGiveaway',
    findExistingUsing: indexer,
  } as AppDetails
  const appClient = new VerifiableGiveawayClient(appDetails, algodClient)

  const {
    isStale: latestCommitmentQIsStale,
    isPending: latestCommitmentQIsPending,
    isError: latestCommitmentQIsError,
    data: latestCommitmentQData,
    refetch: latestCommitmentQRefetch,
  } = useQuery({
    queryKey: ['latestCommitment'],
    queryFn: async () => {
      const { activeCommitment } = await appClient.getLocalState(activeAddress!)
      const acBytes = activeCommitment!.asByteArray()
      return {
        tx_id: base32.encode(acBytes.slice(0, 32)).slice(0, 52),
        block: decodeUint64(acBytes.slice(32, 40), 'safe'),
        participants: decodeUint64(acBytes.slice(40, 41), 'safe'),
        winners: decodeUint64(acBytes.slice(41, 42), 'safe'),
      }
    },
    staleTime: Infinity,
  })

  const callCommitMethod = async () => {
    setLoading(true)

    try {
      const { appId } = await appClient.appClient.getAppReference()
      const accountInfo = (await indexer.lookupAccountByID(activeAddress!).do()) as AccountLookupResult
      const accountOptInStatus =
        accountInfo.account['apps-local-state']?.find((localState: AppLocalState) => localState.id === appId) !== undefined

      const commitArgs = {
        delay: Number(commitmentDelay),
        participants: Number(commitmentParticipants),
        winners: Number(commitmentWinners),
      }
      const response = await (accountOptInStatus ? appClient.commit(commitArgs) : appClient.optIn.commit(commitArgs))
      await latestCommitmentQRefetch()

      setNewCommitmentID(response.transaction.txID())
    } catch (e) {
      // @ts-expect-error We expect the error object to have a message property.
      enqueueSnackbar(e.message, { variant: `error` })
    } finally {
      setLoading(false)
    }
  }

  const callRevealMethod = async () => {
    setLoading(true)

    try {
      const response = await appClient.reveal(
        {},
        {
          apps: [Number(import.meta.env.VITE_RANDOMNESS_BEACON_ID)],
          sendParams: { fee: microAlgos(2_000 + latestCommitmentQData!.winners * 1_000 + 1_000) },
        },
      )
      await latestCommitmentQRefetch()

      const [revealedCommittedID, winners] = response.return!

      setNewRevealID(response.transaction.txID())
      setRevealedCommitmentID(base32.encode(revealedCommittedID).slice(0, 52))
      setRevealedWinners(winners.toString())
    } catch (e) {
      enqueueSnackbar('Reveal failed: try again in 15 seconds.', { variant: `error` })
    } finally {
      setLoading(false)
    }
  }

  return (
    <dialog id="appcalls_modal" className={`modal ${openModal ? 'modal-open' : ''} bg-slate-200`}>
      <form method="dialog" className="modal-box">
        <h3 className="font-bold text-lg">Commit to a giveaway & Reveal the winners</h3>
        <h3 className="font-bold text-lg">Commit</h3>
        <br />
        <input
          type="number"
          placeholder="Commitment delay"
          className="input input-bordered w-full"
          value={commitmentDelay}
          onChange={(e) => {
            setCommitmentDelay(e.target.value)
          }}
        />
        <br />
        <br />
        <input
          type="number"
          placeholder="Number of participants"
          className="input input-bordered w-full"
          value={commitmentParticipants}
          onChange={(e) => {
            setCommitmentParticipants(e.target.value)
          }}
        />
        <br />
        <br />
        <input
          type="number"
          placeholder="Number of winners"
          className="input input-bordered w-full"
          value={commitmentWinners}
          onChange={(e) => {
            setCommitmentWinners(e.target.value)
          }}
        />
        <br />
        <br />
        <h1 className="font-bold">New commitment ID</h1>
        <input type="text" className="input input-bordered w-full" readOnly={true} value={newCommitmentID} />
        <br />
        <h1 className="font-bold">Latest Commitment ID</h1>
        <input
          type="text"
          className="input input-bordered w-full"
          readOnly={true}
          value={
            latestCommitmentQIsError
              ? 'Not found'
              : latestCommitmentQIsPending || latestCommitmentQIsStale
                ? 'loading...'
                : latestCommitmentQData?.tx_id
          }
        />
        <br />
        <br />
        <h3 className="font-bold text-lg">Reveal</h3>
        <br />
        <h1 className="font-bold">New Reveal ID</h1>
        <input type="text" className="input input-bordered w-full" readOnly={true} value={newRevealID} />
        <br />
        <h1 className="font-bold">Revealed Commitment ID</h1>
        <input type="text" className="input input-bordered w-full" readOnly={true} value={revealedCommitmentID} />
        <br />
        <h1 className="font-bold">Revealed Winners</h1>
        <input type="text" className="input input-bordered w-full" readOnly={true} value={revealedWinners} />
        <br />
        <br />
        <div className="modal-action ">
          <button className="btn" onClick={() => setModalState(!openModal)}>
            Close
          </button>
          <button className={`btn`} onClick={callCommitMethod}>
            {loading ? <span className="loading loading-spinner" /> : 'Commit'}
          </button>
          <button
            className={`btn`}
            disabled={latestCommitmentQIsPending || latestCommitmentQIsStale || latestCommitmentQIsError}
            onClick={callRevealMethod}
          >
            {loading ? <span className="loading loading-spinner" /> : 'Reveal'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

export default AppCalls
