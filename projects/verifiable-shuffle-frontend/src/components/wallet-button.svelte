<script lang="ts">
	import { useWallet } from '@txnlab/use-wallet-svelte';
	import { ellipseAddress } from '$lib/utils';

	const { wallets, isReady, activeAddress, activeWallet } = useWallet();

	let connecting = $state(false);
	let showModal = $state(false);

	const handleConnectClick = () => {
		showModal = true;
	};

	const connectWallet = async (walletId: string) => {
		const wallet = wallets.find((w) => w.id === walletId);
		if (!wallet) return;

		connecting = true;
		showModal = false;
		try {
			await wallet.connect();
		} catch (error) {
			console.error(`Failed to connect to ${walletId}:`, error);
		} finally {
			connecting = false;
		}
	};

	const handleDisconnect = async () => {
		const wallet = activeWallet();
		if (!wallet) return;
		connecting = true;
		try {
			await wallet.disconnect();
		} catch (error) {
			console.error('Failed to disconnect:', error);
		} finally {
			connecting = false;
		}
	};
</script>

{#if !isReady()}
	<button disabled>Loading...</button>
{:else if !activeAddress.current}
	<button disabled={connecting} onclick={handleConnectClick}>Connect</button>
{:else}
	<button disabled={connecting} onclick={handleDisconnect}>
		{ellipseAddress(activeAddress.current ?? '')}
	</button>
{/if}

{#if showModal}
	<div
		class="modal-backdrop"
		onclick={() => (showModal = false)}
		onkeydown={(e) => e.key === 'Escape' && (showModal = false)}
		role="presentation"
	>
		<div
			class="modal-content"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			tabindex="-1"
		>
			<h3>Select Wallet</h3>
			<div class="wallet-options">
				{#each wallets as wallet (wallet.id)}
					<button onclick={() => connectWallet(wallet.id)}>
						<img src={wallet.metadata.icon} alt={wallet.metadata.name} />
						<span>{wallet.metadata.name}</span>
					</button>
				{/each}
			</div>
			<button class="close-btn" onclick={() => (showModal = false)}>Cancel</button>
		</div>
	</div>
{/if}

<style>
	.modal-backdrop {
		position: fixed;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		justify-content: center;
		align-items: center;
		z-index: 1000;
	}

	.modal-content {
		background: white;
		padding: 2rem;
		border-radius: 8px;
		min-width: 300px;
		box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
		color: #333;
	}

	h3 {
		margin-top: 0;
		margin-bottom: 1.5rem;
		text-align: center;
	}

	.wallet-options {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.wallet-options button {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1rem;
		border: 1px solid #ddd;
		border-radius: 6px;
		background: white;
		cursor: pointer;
		transition: background 0.2s;
		color: #333;
		font-weight: 500;
		width: 100%;
	}

	.wallet-options button:hover {
		background: #f8f9fa;
		border-color: #007bff;
	}

	.wallet-options img {
		width: 24px;
		height: 24px;
	}

	.close-btn {
		width: 100%;
		padding: 0.5rem;
		background: none;
		border: none;
		color: #666;
		cursor: pointer;
		font-size: 0.9rem;
	}

	.close-btn:hover {
		text-decoration: underline;
	}
</style>
