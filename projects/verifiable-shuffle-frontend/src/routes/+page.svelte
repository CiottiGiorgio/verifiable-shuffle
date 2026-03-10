<script lang="ts">
	import { createShuffleClient } from '$lib/shuffle-client.svelte';
	import { microAlgos } from '@algorandfoundation/algokit-utils';
	import { createBlockchainMonitor } from '$lib/blockchain-monitor.svelte';
	import { retry } from '$lib/retry';
	import { useWallet } from '@txnlab/use-wallet-svelte';

	const { activeAddress } = useWallet();
	// Reactive shuffle client that automatically updates when wallet state changes
	const { algorandClient, factory: shuffleAppFactory, getAppClient } = createShuffleClient();

	const monitor = createBlockchainMonitor(
		algorandClient.client.algod
	);

	// Track loading state to disable buttons during execution
	let isExecuting = $state(false);
	let latestRandomResult: number[] | undefined = $state();

	/**
	 * Handle commit action. Type-safe: only called when wallet is connected.
	 */
	const handleWorkflow = async () => {
		isExecuting = true;
		try {
			// Get the app client (performs blockchain query to find deployed contract)
			const shuffleClient = await getAppClient();
			if (!shuffleClient) return; // Should never happen due to button disabled state

			const address = activeAddress.current!;

			const isOptedIn =
				(await shuffleClient.algorand.account.getInformation(address)).appsLocalState?.find(
					(state) => state.id === shuffleClient.appId
				) !== undefined;

			// Build and send transaction group
			const onCompleteCommitGroup = !isOptedIn
				? shuffleClient.newGroup().optIn
				: shuffleClient.newGroup();

			await onCompleteCommitGroup
				.commit({
					args: { delay: 1, participants: 2, winners: 1 },
					maxFee: microAlgos(10_000)
				})
				.send({ populateAppCallResources: true, coverAppCallInnerTransactionFees: true });

			const targetRevealRound = (await shuffleClient.state.local(address).commitment())?.round;
			if (!targetRevealRound) return; // Should never happen since a commit went through

			while (monitor.round < targetRevealRound) {
				await new Promise((resolve) => setTimeout(resolve, 1000));
			}

			// We waited enough, but the randomness beacon could still not have uploaded the VRF for the target round.
			const randomness = await retry(() =>
				shuffleClient
					.newGroup()
					.closeOut.reveal({ args: {}, maxFee: microAlgos(10_000) })
					.send({ populateAppCallResources: true, coverAppCallInnerTransactionFees: true })
			);

			latestRandomResult = randomness.returns[0]?.winners;
		} finally {
			isExecuting = false;
		}
	};
</script>

<div>
	<p>round: {monitor.round}</p>
	<button disabled={!shuffleAppFactory || isExecuting} onclick={handleWorkflow}>
		Pick a winner
	</button>
	{#if latestRandomResult}
		<p>{latestRandomResult.join(', ')}</p>
	{/if}
</div>
