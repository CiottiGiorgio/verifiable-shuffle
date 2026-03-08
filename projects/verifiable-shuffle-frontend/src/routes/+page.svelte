<script lang="ts">
	import { useWallet } from '@txnlab/use-wallet-svelte';
	import { VerifiableShuffleFactory } from '../contracts/VerifiableShuffle.ts';
	import {
		getAlgodConfigFromSvelteEnvironment,
		getIndexerConfigFromSvelteEnvironment
	} from '$lib/config';
	import { AlgorandClient, microAlgos } from '@algorandfoundation/algokit-utils';
	import { PUBLIC_APP_CREATOR } from '$env/static/public';

	const { activeAddress, activeWallet, transactionSigner } = useWallet();

	const algodConfig = getAlgodConfigFromSvelteEnvironment();
	const indexerConfig = getIndexerConfigFromSvelteEnvironment();
	const algorandClient = AlgorandClient.fromConfig({ algodConfig, indexerConfig });
	algorandClient.setDefaultSigner(transactionSigner);

	const handleCommit = async () => {
		const shuffleFactory = new VerifiableShuffleFactory({
			algorand: algorandClient,
			defaultSender: activeAddress.current ?? undefined
		});
		const shuffleClient = await shuffleFactory.getAppClientByCreatorAndName({
			creatorAddress: PUBLIC_APP_CREATOR
		});

		const simResult = await shuffleClient
			.newGroup()
      .optIn
			.commit({
				args: { delay: 1, participants: 5, winners: 3 },
				extraFee: microAlgos(10_000) // Adds 10_000 microAlgos to the standard fee
			})
			.simulate({ allowUnnamedResources: true });
		console.log(simResult);
	};
</script>

<div>
	<button onclick={handleCommit}>Commit</button>
</div>
