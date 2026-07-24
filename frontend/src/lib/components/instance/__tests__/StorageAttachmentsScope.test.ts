import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('$lib/api/client', () => ({
	api: { get, post: vi.fn(), delete: vi.fn() },
	ApiError: class ApiError extends Error {},
}));

import ScopeWrapper from './_StorageAttachmentsScopeWrapper.svelte';

function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((res) => { resolve = res; });
	return { promise, resolve };
}

const catalog = [{ id: 'storage-a', name: 'storage-a', status: 'available', share_proto: 'NFS' }];

describe('StorageAttachmentsSection reactive scope ownership', () => {
	beforeEach(() => vi.clearAllMocks());

	it('retains a loaded project catalog across same-project missing and instance transitions', async () => {
		get.mockImplementation((path: string) => path === '/api/v1/file-storage' ? Promise.resolve(catalog) : Promise.resolve([]));
		render(ScopeWrapper);
		await waitFor(() => expect(get).toHaveBeenCalledWith('/api/v1/instances/instance-a/storage-attachments', undefined, 'project-a'));
		await fireEvent.click(screen.getByRole('button', { name: '+ 연결' }));
		await screen.findByRole('option', { name: /storage-a/ });
		expect(get.mock.calls.filter(([path]) => path === '/api/v1/file-storage')).toHaveLength(1);

		await fireEvent.click(screen.getByTestId('clear-instance'));
		await fireEvent.click(screen.getByTestId('set-instance-b'));
		await waitFor(() => expect(get).toHaveBeenCalledWith('/api/v1/instances/instance-b/storage-attachments', undefined, 'project-a'));
		await fireEvent.click(screen.getByRole('button', { name: '+ 연결' }));
		expect(await screen.findByRole('option', { name: /storage-a/ })).toBeTruthy();
		expect(get.mock.calls.filter(([path]) => path === '/api/v1/file-storage')).toHaveLength(1);
	});

	it('discards stale A-to-B-to-A attachment completions', async () => {
		const firstA = deferred<unknown[]>();
		const b = deferred<unknown[]>();
		const finalA = deferred<unknown[]>();
		get.mockImplementation((path: string) => {
			if (path.includes('/instances/instance-a/')) {
				return get.mock.calls.filter(([called]) => called === path).length === 1 ? firstA.promise : finalA.promise;
			}
			if (path.includes('/instances/instance-b/')) return b.promise;
			return Promise.resolve(catalog);
		});
		render(ScopeWrapper);
		await fireEvent.click(screen.getByTestId('set-instance-b'));
		await fireEvent.click(screen.getByTestId('set-instance-a'));
		firstA.resolve([{ file_storage_id: 'stale-a', name: 'stale-a', share_proto: 'NFS', status: 'available' }]);
		b.resolve([{ file_storage_id: 'stale-b', name: 'stale-b', share_proto: 'NFS', status: 'available' }]);
		finalA.resolve([]);
		await waitFor(() => expect(screen.getByText('연결된 파일 스토리지가 없습니다.')).toBeTruthy());
		expect(screen.queryByText('stale-a')).toBeNull();
		expect(screen.queryByText('stale-b')).toBeNull();
	});
});
