<script lang="ts">
	import { useWallet, type Wallet, WalletId } from '@txnlab/use-wallet-svelte';
	import { ellipseAddress } from '$lib/utils';

	const {
		wallets, // List of available wallets
		activeWallet, // Currently active wallet (function)
		isReady,
		activeWalletAccounts,
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

	const setActiveAccount = (event: Event, wallet: Wallet) => {
		const selectElement = event.target as HTMLSelectElement;
		wallet.setActiveAccount(selectElement.value);
	};
</script>

{#if !isReady()}
	<button disabled>Loading...</button>
{:else if !luteWallet}
	<button disabled>Error loading Lute</button>
{:else if !activeAddress.current}
	<button disabled={connecting} onclick={() => handleConnect()}>Connect</button>
{:else}
	<button disabled={connecting} onclick={() => luteWallet.disconnect()}
		>{ellipseAddress(activeAddress.current)}</button
	>
{/if}
