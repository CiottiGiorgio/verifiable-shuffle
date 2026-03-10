import type { AlgorandClient } from '@algorandfoundation/algokit-utils';

export function createBlockchainMonitor(client: AlgorandClient['client']['algod']) {
	let round: bigint = $state(0n);

	async function poll() {
		const status = await client.statusAfterBlock(round).do();
		round = status['lastRound'];
		poll(); // Continue long polling
	}

	poll();

	return {
		get round() {
			return round;
		}
	};
}
