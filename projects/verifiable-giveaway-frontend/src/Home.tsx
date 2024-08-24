// src/components/Home.tsx
import { useWallet } from '@txnlab/use-wallet'
import React, { useState } from 'react'
import ConnectWallet from './components/ConnectWallet'
import AppCalls from './components/AppCalls'

interface HomeProps {}

const Home: React.FC<HomeProps> = () => {
  const [openWalletModal, setOpenWalletModal] = useState<boolean>(false)
  const [appCallsModal, setAppCallsModal] = useState<boolean>(false)
  const { activeAddress } = useWallet()

  const toggleWalletModal = () => {
    setOpenWalletModal(!openWalletModal)
  }

  const toggleAppCallsModal = () => {
    setAppCallsModal(!appCallsModal)
  }

  return (
    <div className="hero min-h-screen bg-teal-400">
      <div className="hero-content text-center rounded-lg p-6 max-w-md bg-white mx-auto">
        <div className="max-w-md">
          <h1 className="text-4xl">
            Welcome to <div className="font-bold">Verifiable Giveaway</div>
          </h1>
          <div className="divider" />
          <button data-test-id="connect-wallet" className="btn m-2" onClick={toggleWalletModal}>
            Wallet Connection
          </button>

          {activeAddress && (
            <button data-test-id="appcalls-demo" className="btn m-2" onClick={toggleAppCallsModal}>
              Commit & Reveal
            </button>
          )}
          <div className="divider" />
          <h1 className="text-2xl">Disclaimer</h1>
          <p className="py-6">
            This software is distributed under{' '}
            <a href="https://github.com/CiottiGiorgio/verifiable-giveaway/blob/1040e3a78dfc2cefcc7e7ea9f52de33394243c4a/LICENSE">
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
          <div className="divider" />
          <h1 className="text-2xl">AlgoKit</h1>
          <p className="py-6">This starter has been generated using official AlgoKit React template.</p>

          <div className="grid">
            <a
              data-test-id="getting-started"
              className="btn btn-primary m-2"
              target="_blank"
              href="http://algokit.io"
            >
              Learn about AlgoKit
            </a>
          </div>

          <ConnectWallet openModal={openWalletModal} closeModal={toggleWalletModal} />
          <AppCalls openModal={appCallsModal} setModalState={setAppCallsModal} />
        </div>
      </div>
    </div>
  )
}

export default Home
