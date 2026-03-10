<script lang="ts">
	import { createShuffleClient } from '$lib/shuffle-client.svelte';
	import { microAlgos } from '@algorandfoundation/algokit-utils';
	import { createBlockchainMonitor } from '$lib/blockchain-monitor.svelte';
	import { retry } from '$lib/retry';
	import { useWallet } from '@txnlab/use-wallet-svelte';

	const { activeAddress } = useWallet();
	// Reactive shuffle client that automatically updates when wallet state changes
	const { algorandClient, factory: shuffleAppFactory, getAppClient } = createShuffleClient();

	const monitor = createBlockchainMonitor(algorandClient.client.algod);

	// Constants for fee calculation
	const COMMIT_SINGLE_WINNER_OP_COST = 600;
	const REVEAL_SINGLE_WINNER_OP_COST = 500;
	const MIN_TXN_FEE = 1000;

	// Track loading state to disable buttons during execution
	let isExecuting = $state(false);
	let latestRandomResult: number[] | undefined = $state();
	let workflowStatus = $state('');

	// Form state
	let participants = $state(2);
	let winners = $state(1);

	// Derived estimates (matching Python test logic)
	const commitEstimate = $derived(
		microAlgos((Math.floor((winners * COMMIT_SINGLE_WINNER_OP_COST) / 700) + 2) * MIN_TXN_FEE)
	);
	const revealEstimate = $derived(
		microAlgos((Math.floor((winners * REVEAL_SINGLE_WINNER_OP_COST) / 700) + 2) * MIN_TXN_FEE)
	);

	/**
	 * Handle commit action. Type-safe: only called when wallet is connected.
	 */
	const handleWorkflow = async () => {
		isExecuting = true;
		workflowStatus = 'waiting to commit';
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
					args: { delay: 1, participants, winners },
					maxFee: microAlgos(commitEstimate.microAlgos + BigInt(5 * MIN_TXN_FEE))
				})
				.send({ populateAppCallResources: true, coverAppCallInnerTransactionFees: true });

			const targetRevealRound = (await shuffleClient.state.local(address).commitment())?.round;
			if (!targetRevealRound) return; // Should never happen since a commit went through

			workflowStatus = 'waiting for the target round';
			while (monitor.round < targetRevealRound) {
				await new Promise((resolve) => setTimeout(resolve, 1000));
			}

			// We waited enough, but the randomness beacon could still not have uploaded the VRF for the target round.
			workflowStatus = 'waiting for the randomness beacon to upload a VRF for that round';
			await retry(async () => {
				return await shuffleClient
					.newGroup()
					.closeOut.reveal({ args: {}, extraFee: revealEstimate })
					.simulate({ skipSignatures: true, allowUnnamedResources: true });
			});

			workflowStatus = 'waiting to reveal';
			const randomness = await shuffleClient.send.closeOut.reveal({
				args: {},
				maxFee: microAlgos(revealEstimate.microAlgos + BigInt(5 * MIN_TXN_FEE)),
				populateAppCallResources: true,
				coverAppCallInnerTransactionFees: true
			});

			latestRandomResult = randomness.return?.winners;
			workflowStatus = 'revealed';
		} catch (e) {
			console.error(e);
			workflowStatus = 'last attempt failed';
		} finally {
			isExecuting = false;
		}
	};
</script>

<div class="container">
	<p>Current round: {monitor.round}</p>

	<div class="form-group">
		<label for="participants">Number of participants:</label>
		<input
			id="participants"
			type="number"
			bind:value={participants}
			min="1"
			disabled={isExecuting}
		/>
	</div>

	<div class="form-group">
		<label for="winners">Number of winners:</label>
		<input
			id="winners"
			type="number"
			bind:value={winners}
			min="1"
			max={participants}
			disabled={isExecuting}
		/>
	</div>

	<div class="fee-info">
		<p>Estimated Commit Fee: {commitEstimate.algo} ALGO</p>
		<p>Estimated Reveal Fee: {revealEstimate.algo} ALGO</p>
	</div>

	<button
		disabled={!shuffleAppFactory || isExecuting || winners > participants || winners < 1}
		onclick={handleWorkflow}
	>
		{isExecuting ? 'Processing...' : 'Pick winners'}
	</button>

	{#if workflowStatus}
		<p class="status">Status: {workflowStatus}</p>
	{/if}

	{#if latestRandomResult}
		<div class="result">
			<h3>Winners (starting at 0):</h3>
			<p>{latestRandomResult.join(', ')}</p>
		</div>
	{/if}
</div>

<style>
	.container {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 400px;
		margin: 2rem auto;
		padding: 1rem;
		border: 1px solid #ccc;
		border-radius: 8px;
	}
	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.fee-info {
		font-size: 0.85rem;
		color: #555;
		background: #f9f9f9;
		padding: 0.5rem;
		border-radius: 4px;
	}
	.buffer-note {
		font-size: 0.75rem;
		color: #888;
		margin-top: 0.25rem;
	}
	.status {
		font-style: italic;
		color: #666;
	}
	.result {
		margin-top: 1rem;
		padding: 1rem;
		background-color: #f0f9ff;
		border-radius: 4px;
	}
</style>
