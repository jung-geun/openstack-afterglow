import { beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));


const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function jsonResponse(value: unknown): Response {
	return new Response(JSON.stringify(value), {
		status: 200,
		headers: { 'Content-Type': 'application/json' },
	});
}

describe('streamK3sProgress cache fencing', () => {
	beforeEach(() => {
		vi.resetModules();
		mockFetch.mockReset();
		localStorage.clear();
		sessionStorage.clear();
	});

	it('invalidates warm reads before opening and after closing the mutating stream', async () => {
		const emptyStream = new ReadableStream<Uint8Array>({
			start(controller) { controller.close(); },
		});
		mockFetch
			.mockResolvedValueOnce(jsonResponse({ source: 'warm' }))
			.mockResolvedValueOnce(new Response(emptyStream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
			.mockResolvedValueOnce(jsonResponse({ source: 'visible' }));
		const { api } = await import('$lib/api/client');
		const { streamK3sProgress } = await import('../k3sSseStream');
		await api.prefetch('/api/v1/items', 'token', 'project');

		for await (const _message of streamK3sProgress('/api/v1/k3s/clusters/async', { method: 'POST', body: {}, token: 'token', projectId: 'project' })) {
			throw new Error('empty stream must not emit');
		}

		await expect(api.get('/api/v1/items', 'token', 'project')).resolves.toEqual({ source: 'visible' });
		expect(mockFetch).toHaveBeenCalledTimes(3);
	});
});
