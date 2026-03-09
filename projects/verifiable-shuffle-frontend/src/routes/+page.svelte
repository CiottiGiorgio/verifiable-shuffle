<script lang="ts">
	import { createShuffleClient } from '$lib/shuffle-client.svelte';
	import { microAlgos } from '@algorandfoundation/algokit-utils';

	// Reactive shuffle client that automatically updates when wallet state changes
	const shuffleClientManager = createShuffleClient();

	// Track loading state to disable buttons during execution
	let isExecuting = $state(false);

	/**
	 * Handle commit action. Type-safe: only called when wallet is connected.
	 */
	const handleCommit = async () => {
		isExecuting = true;
		try {
			// Get the app client (performs blockchain query to find deployed contract)
			const shuffleClient = await shuffleClientManager.getAppClient();
			if (!shuffleClient) return; // Should never happen due to button disabled state

			const address = shuffleClientManager.address!;

			const isOptedIn = (
				await shuffleClient.algorand.account.getInformation(address)
			).appsLocalState?.find((state) => state.id === shuffleClient.appId) !== undefined;

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
		} finally {
			isExecuting = false;
		}
	};

	/**
	 * Handle reveal action. Type-safe: only called when wallet is connected.
	 */
	const handleReveal = async () => {
		isExecuting = true;
		try {
			// Get the app client (performs blockchain query to find deployed contract)
			const shuffleClient = await shuffleClientManager.getAppClient();
			if (!shuffleClient) return; // Should never happen due to button disabled state

			const randomness = await shuffleClient
				.newGroup()
				.closeOut.reveal({ args: {}, maxFee: microAlgos(10_000) })
				.send({ populateAppCallResources: true, coverAppCallInnerTransactionFees: true });

			console.log(randomness.returns[0]?.winners);
		} finally {
			isExecuting = false;
		}
	};
</script>

<div>
	<button disabled={!shuffleClientManager.factory || isExecuting} onclick={handleCommit}>
		Commit
	</button>
	<button disabled={!shuffleClientManager.factory || isExecuting} onclick={handleReveal}>
		Reveal
	</button>
</div>
