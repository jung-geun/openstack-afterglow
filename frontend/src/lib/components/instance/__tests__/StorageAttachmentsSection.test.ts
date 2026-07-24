import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import type { InstanceDetailController } from '$lib/stores/instanceDetailController.svelte';

const { controllerRef, get, post } = vi.hoisted(() => ({
	controllerRef: { current: undefined as unknown },
	get: vi.fn(),
	post: vi.fn(),
}));

vi.mock('$lib/stores/instanceDetailController.svelte', () => ({
	useInstanceDetailController: () => controllerRef.current,
}));
vi.mock('$lib/api/client', () => ({
	api: { get, post, delete: vi.fn() },
	ApiError: class ApiError extends Error {},
}));


function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((res) => { resolve = res; });
	return { promise, resolve };
}
import StorageAttachmentsSection from '../StorageAttachmentsSection.svelte';

function renderSection(instanceId?: string, projectId?: string) {
	controllerRef.current = {
		instanceId,
		effectiveProjectId: projectId,
	} as InstanceDetailController;
	return render(StorageAttachmentsSection);
}

describe('StorageAttachmentsSection request ownership', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		get.mockResolvedValue([]);
	});

	it('waits for both scope primitives and loads attachments without preloading the catalog', async () => {
		renderSection('instance-a', undefined);
		await Promise.resolve();
		expect(get).not.toHaveBeenCalled();

		renderSection('instance-a', 'project-a');
		await waitFor(() => expect(get).toHaveBeenCalledWith(
			'/api/v1/instances/instance-a/storage-attachments',
			undefined,
			'project-a',
		));
		expect(get).not.toHaveBeenCalledWith('/api/v1/file-storage', undefined, 'project-a');
	});

	it('loads the project catalog only when the attach form opens', async () => {
		renderSection('instance-a', 'project-a');
		await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
		await fireEvent.click(screen.getByRole('button', { name: /연결/ }));
		await waitFor(() => expect(get).toHaveBeenCalledWith(
			'/api/v1/file-storage',
			undefined,
			'project-a',
		));
	});

	it('clears attachment busy state after its post-mutation reload', async () => {
		const reload = deferred<unknown[]>();
		get
			.mockResolvedValueOnce([])
			.mockResolvedValueOnce([{ id: 'storage-a', name: 'storage-a', status: 'available', share_proto: 'NFS' }])
			.mockReturnValueOnce(reload.promise);
		post.mockResolvedValue({ mount_command: 'mount storage-a', keyring_file: null });
		renderSection('instance-a', 'project-a');
		await waitFor(() => expect(get).toHaveBeenCalledTimes(1));

		await fireEvent.click(screen.getByRole('button', { name: '+ 연결' }));
		await screen.findByRole('option', { name: /storage-a/ });
		await fireEvent.change(screen.getByRole('combobox'), { target: { value: 'storage-a' } });
		await fireEvent.input(screen.getByPlaceholderText('/mnt/mydata'), { target: { value: '/mnt/data' } });
		await fireEvent.click(screen.getByRole('button', { name: '연결' }));
		await waitFor(() => expect(post).toHaveBeenCalledTimes(1));

		await fireEvent.click(screen.getByRole('button', { name: '+ 연결' }));
		expect(screen.getByRole('button', { name: '연결 중...' }).hasAttribute('disabled')).toBe(true);
		reload.resolve([]);
		await waitFor(() => expect(screen.getByRole('button', { name: '연결' })).toBeTruthy());
		await fireEvent.change(screen.getByRole('combobox'), { target: { value: 'storage-a' } });
		await fireEvent.input(screen.getByPlaceholderText('/mnt/mydata'), { target: { value: '/mnt/data' } });
		expect(screen.getByRole('button', { name: '연결' }).hasAttribute('disabled')).toBe(false);
	});
});
