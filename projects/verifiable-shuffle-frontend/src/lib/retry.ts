/**
 * Retries an async function with a fixed interval and maximum total time.
 * @param fn The async function to retry
 * @param intervalMs Interval between retries in milliseconds (default: 3000)
 * @param maxTimeMs Maximum total time to spend retrying in milliseconds (default: 20000)
 * @returns The result of the function if successful
 * @throws The last error encountered if all retries fail
 */
export async function retry<T>(
	fn: () => Promise<T>,
	intervalMs: number = 3000,
	maxTimeMs: number = 36000
): Promise<T> {
	const startTime = Date.now();
	let lastError: unknown;

	while (Date.now() - startTime < maxTimeMs) {
		try {
			return await fn();
		} catch (error) {
			lastError = error;
			await new Promise((resolve) => setTimeout(resolve, intervalMs));
		}
	}

	throw lastError;
}
