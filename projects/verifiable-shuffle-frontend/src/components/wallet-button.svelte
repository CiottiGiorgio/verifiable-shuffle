<script lang="ts">
	import { useWallet, WalletId } from '@txnlab/use-wallet-svelte';
	import { ellipseAddress } from '$lib/utils';

	const {
		wallets, // List of available wallets
		isReady,
		activeAddress
	} = useWallet();
	let luteWallet = $derived(wallets.find((wallet) => wallet.id === WalletId.LUTE));
	let connecting = $state(false);

	const handleConnect = async () => {
		connecting = true;
		try {
			await luteWallet?.connect();
		} catch (error) {
			console.error('Failed to connect:', error);
		} finally {
			connecting = false;
		}
	};

	const handleDisconnect = async () => {
		connecting = true;
		try {
			await luteWallet?.disconnect();
		} catch (error) {
			console.error('Failed to disconnect:', error);
		} finally {
			connecting = false;
		}
	};
</script>

{#if !isReady()}
	<button disabled>Loading...</button>
{:else if !luteWallet}
	<button disabled>Error loading Lute</button>
{:else if !activeAddress.current}
	<button disabled={connecting} onclick={handleConnect}>Connect</button>
{:else}
	<button disabled={connecting} onclick={handleDisconnect}
		>{ellipseAddress(activeAddress.current)}</button
	>
{/if}
