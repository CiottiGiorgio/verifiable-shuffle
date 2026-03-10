<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { WalletManager, WalletId, NetworkId, useWalletContext } from '@txnlab/use-wallet-svelte';
	import WalletButton from '../components/wallet-button.svelte';

	// Create manager instance (moved from wallet-button.svelte)
	useWalletContext(
		new WalletManager({
			wallets: [WalletId.LUTE, WalletId.PERA],
			defaultNetwork: NetworkId.TESTNET
		})
	);

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<header>
	<nav>
		<div class="logo">
			<span>Verifiable Shuffle</span>
		</div>
		<div class="actions">
			<WalletButton />
		</div>
	</nav>
</header>

<main>
	{@render children()}
</main>

<style>
	:global(body) {
		margin: 0;
		font-family:
			-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans',
			'Helvetica Neue', sans-serif;
	}

	header {
		border-bottom: 1px solid #eee;
		padding: 1rem 2rem;
	}

	nav {
		display: flex;
		justify-content: space-between;
		align-items: center;
		max-width: 1200px;
		margin: 0 auto;
	}

	.logo span {
		font-weight: bold;
		font-size: 1.25rem;
		text-decoration: none;
		color: inherit;
	}

	.actions :global(button) {
		padding: 0.5rem 1rem;
		background-color: #007bff;
		color: white;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		font-weight: 500;
	}

	.actions :global(button:hover) {
		background-color: #0056b3;
	}

	main {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem;
	}
</style>
