<script lang="ts">
	import { createShuffleClient } from '$lib/shuffle-client.svelte';
	import { microAlgos } from '@algorandfoundation/algokit-utils';
	import { createBlockchainMonitor } from '$lib/blockchain-monitor.svelte';
	import { retry } from '$lib/retry';

	// Reactive shuffle client that automatically updates when wallet state changes
	const shuffleClientManager = createShuffleClient();

	let roundMonitor: { readonly round: bigint } | undefined = $state();

	// Track loading state to disable buttons during execution
	let isExecuting = $state(false);
	let latestRandomResult: number[] | undefined = $state(undefined);

	$effect(() => {
		if (shuffleClientManager.factory) {
			roundMonitor = createBlockchainMonitor(shuffleClientManager.factory.algorand.client.algod);
		}
	});

	/**
	 * Handle commit action. Type-safe: only called when wallet is connected.
	 */
	const handleWorkflow = async () => {
		isExecuting = true;
		try {
			// Get the app client (performs blockchain query to find deployed contract)
			const shuffleClient = await shuffleClientManager.getAppClient();
			if (!shuffleClient) return; // Should never happen due to button disabled state

			const address = shuffleClientManager.address!;

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

			if (!roundMonitor) return; // Should never happen
			while (roundMonitor.round < Number(targetRevealRound)) {
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
	<button disabled={!shuffleClientManager.factory || isExecuting} onclick={handleWorkflow}>
		Pick a winner
	</button>
	{#if latestRandomResult}
		<p>{latestRandomResult.join(', ')}</p>
	{/if}
</div>
