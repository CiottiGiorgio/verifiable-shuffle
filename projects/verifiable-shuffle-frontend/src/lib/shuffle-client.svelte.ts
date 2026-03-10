import { useWallet } from '@txnlab/use-wallet-svelte';
import {
	VerifiableShuffleFactory,
	type VerifiableShuffleClient
} from '../contracts/VerifiableShuffle.ts';
import {
	getAlgodConfigFromSvelteEnvironment,
	getIndexerConfigFromSvelteEnvironment
} from '$lib/config';
import { AlgorandClient } from '@algorandfoundation/algokit-utils';
import { PUBLIC_APP_CREATOR } from '$env/static/public';

/**
 * Creates a reactive shuffle client that automatically updates when the wallet state changes.
 * Returns null when no wallet is connected, providing compile-time guarantees for type safety.
 */
export function createShuffleClient() {
	const { activeAddress, transactionSigner } = useWallet();

	// Reactive state that updates when activeAddress changes
	const shuffleFactory = $derived.by(() => {
		const address = activeAddress.current;

		// If there is no active address, we cannot sign or identify the sender.
		if (!address) {
			return null;
		}

		// Create a new AlgorandClient with updated signer
		const algodConfig = getAlgodConfigFromSvelteEnvironment();
		const indexerConfig = getIndexerConfigFromSvelteEnvironment();
		const algorandClient = AlgorandClient.fromConfig({ algodConfig, indexerConfig });
		
		// transactionSigner is a stable wrapper function from useWallet()
		// that dynamically resolves the correct wallet at execution time.
		algorandClient.setDefaultSigner(transactionSigner);

		// Return a factory configured with the current address
		return new VerifiableShuffleFactory({
			algorand: algorandClient,
			defaultSender: address
		});
	});

	// Async function to get the actual app client (performs blockchain queries)
	async function getAppClient(): Promise<VerifiableShuffleClient | null> {
		const factory = shuffleFactory;
		if (!factory) return null;

		return await factory.getAppClientByCreatorAndName({
			creatorAddress: PUBLIC_APP_CREATOR
		});
	}

	return {
		/**
		 * The shuffle factory, or null if no wallet is connected.
		 * This is reactive and updates automatically when the wallet state changes.
		 */
		get factory() {
			return shuffleFactory;
		},

		/**
		 * Get the app client instance. Returns null if no wallet is connected.
		 * This performs blockchain queries to find the latest deployed contract.
		 */
		getAppClient,

		/**
		 * The currently connected address, or null if no wallet is connected.
		 */
		get address() {
			return activeAddress.current;
		}
	};
}
