import {
	PUBLIC_ALGOD_SERVER,
	PUBLIC_ALGOD_PORT,
	PUBLIC_INDEXER_SERVER,
	PUBLIC_INDEXER_PORT
} from '$env/static/public';

export interface AlgoSvelteClientConfig {
	server: string;
	port?: string;
}

export function getAlgodConfigFromSvelteEnvironment(): AlgoSvelteClientConfig {
	if (!PUBLIC_ALGOD_SERVER) {
		throw new Error(
			'Attempt to get default algod configuration without specifying VITE_ALGOD_SERVER in the environment variables'
		);
	}

	return {
		server: PUBLIC_ALGOD_SERVER,
		port: PUBLIC_ALGOD_PORT
	};
}

export interface IndexerSvelteClientConfig {
	server: string;
	port?: string;
}

export function getIndexerConfigFromSvelteEnvironment(): IndexerSvelteClientConfig {
	if (!PUBLIC_INDEXER_SERVER) {
		throw new Error(
			'Attempt to get default algod configuration without specifying VITE_ALGOD_SERVER in the environment variables'
		);
	}

	return {
		server: PUBLIC_INDEXER_SERVER,
		port: PUBLIC_INDEXER_PORT
	};
}
