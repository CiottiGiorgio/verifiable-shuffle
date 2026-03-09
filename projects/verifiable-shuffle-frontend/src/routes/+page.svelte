<script lang="ts">
	import { useWallet } from '@txnlab/use-wallet-svelte';
	import { VerifiableShuffleFactory } from '../contracts/VerifiableShuffle.ts';
	import {
		getAlgodConfigFromSvelteEnvironment,
		getIndexerConfigFromSvelteEnvironment
	} from '$lib/config';
	import { AlgorandClient, microAlgos } from '@algorandfoundation/algokit-utils';
	import { PUBLIC_APP_CREATOR } from '$env/static/public';

	const { activeAddress, transactionSigner } = useWallet();

	const algodConfig = getAlgodConfigFromSvelteEnvironment();
	const indexerConfig = getIndexerConfigFromSvelteEnvironment();
	const algorandClient = AlgorandClient.fromConfig({ algodConfig, indexerConfig });
	algorandClient.setDefaultSigner(transactionSigner);

	const handleCommit = async () => {
		if (!activeAddress.current) {
			alert('Please connect your wallet first.');
			return;
		}

		const shuffleFactory = new VerifiableShuffleFactory({
			algorand: algorandClient,
			defaultSender: activeAddress.current
		});
		const shuffleClient = await shuffleFactory.getAppClientByCreatorAndName({
			creatorAddress: PUBLIC_APP_CREATOR
		});

		let isOptedIn: boolean;
		try {
			isOptedIn = true;
			await shuffleClient.state.local(activeAddress.current).getAll();
		} catch (error) {
			isOptedIn = false;
		}

		const onCompleteCommitGroup = !isOptedIn
			? shuffleClient.newGroup().optIn
			: shuffleClient.newGroup();
		await onCompleteCommitGroup
			.commit({
				args: { delay: 1, participants: 2, winners: 1 },
				maxFee: microAlgos(10_000)
			})
			.send({ populateAppCallResources: true, coverAppCallInnerTransactionFees: true });
	};

	const handleReveal = async () => {
		if (!activeAddress.current) {
			alert('Please connect your wallet first.');
			return;
		}

		const shuffleFactory = new VerifiableShuffleFactory({
			algorand: algorandClient,
			defaultSender: activeAddress.current
		});
		const shuffleClient = await shuffleFactory.getAppClientByCreatorAndName({
			creatorAddress: PUBLIC_APP_CREATOR
		});

		const randomness = await shuffleClient
			.newGroup()
			.closeOut.reveal({ args: {}, maxFee: microAlgos(10_000) })
			.send({ populateAppCallResources: true, coverAppCallInnerTransactionFees: true });

		console.log(randomness.returns[0]?.winners);
	};
</script>

<div>
	<button onclick={handleCommit}>Commit</button>
	<button onclick={handleReveal}>Reveal</button>
</div>
