// src/components/Home.tsx
import { useWallet } from '@txnlab/use-wallet'
import React, { useState } from 'react'
import ConnectWallet from './components/ConnectWallet'
import Shuffle from './components/Shuffle'

interface HomeProps {}

const Home: React.FC<HomeProps> = () => {
  const [openWalletModal, setOpenWalletModal] = useState<boolean>(false)
  const [openShuffleModal, setOpenShuffleModal] = useState<boolean>(false)
  const { activeAddress } = useWallet()

  const toggleWalletModal = () => {
    setOpenWalletModal(!openWalletModal)
  }

  const toggleShuffleModal = () => {
    setOpenShuffleModal(!openShuffleModal)
  }

  return (
    <div className="hero min-h-screen bg-teal-400">
      <div className="hero-content text-center rounded-lg p-6 max-w-md bg-white mx-auto">
        <div className="max-w-md">
          <h1 className="text-4xl">
            Welcome to <div className="font-bold">Verifiable Shuffle</div>
          </h1>

          <div className="grid">
            <div className="divider" />
            <button data-test-id="connect-wallet" className="btn m-2" onClick={toggleWalletModal}>
              Wallet Connection
            </button>

            {activeAddress && (
              <button data-test-id="application-call" className="btn m-2" onClick={toggleShuffleModal}>
                Send Application Call
              </button>
            )}
            <div className="divider" />
            <h1 className="text-2xl">Disclaimer</h1>
            <p className="py-6">
              This software is distributed under{' '}
              <a href="https://github.com/CiottiGiorgio/verifiable-shuffle/blob/3e541254403a4299823f633d28e5f4a05758905b/LICENSE">
                MIT License
              </a>
              .<br />
              <br />
              In addition to the conditions of use of this software, <a href="https://github.com/CiottiGiorgio">the author</a> declares that
              this software is for demonstration purposes only.
              <br />
              <br />
              While great effort in research, implementation, and testing was put into this project, the author makes no guarantees on the
              quality of the statistical properties resulting from the use of this software.
            </p>
          </div>

          <ConnectWallet openModal={openWalletModal} closeModal={toggleWalletModal} />
          <Shuffle openModal={openShuffleModal} setModalState={setOpenShuffleModal} />
        </div>
      </div>
    </div>
  )
}

export default Home
