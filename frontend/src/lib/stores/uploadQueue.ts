import { get, writable } from 'svelte/store';
import { ApiError, api } from '$lib/api/client';

export interface UploadJob {
	id: string;
	name: string;
	containerName: string;
	prefix: string;
	status: 'uploading' | 'success' | 'error' | 'canceled';
	loaded: number;
	total: number;
	startTime: number;
	error?: string;
	abort?: () => void;
	onComplete?: (job: UploadJob) => void;
}

interface UploadResponse {
	success: boolean;
	name: string;
	bytes: number;
	etag: string;
	content_type?: string;
}

const jobs = writable<UploadJob[]>([]);

function enqueue(
	file: File,
	params: {
		containerName: string;
		prefix?: string;
		token?: string;
		projectId?: string;
		onComplete?: (job: UploadJob) => void;
	}
): string {
	const id = crypto.randomUUID();

	const job: UploadJob = {
		id,
		name: file.name,
		containerName: params.containerName,
		prefix: params.prefix ?? '',
		status: 'uploading',
		loaded: 0,
		total: file.size,
		startTime: Date.now(),
		onComplete: params.onComplete
	};
	jobs.update((arr) => [...arr, job]);

	const formData = new FormData();
	formData.append('file', file, file.name);
	if (params.prefix) formData.append('prefix', params.prefix);

	const { promise, abort } = api.uploadWithProgress<UploadResponse>(
		`/api/object-storage/${encodeURIComponent(params.containerName)}/upload`,
		formData,
		(e) => _patch(id, { loaded: e.loaded }),
		params.token,
		params.projectId
	);
	_patch(id, { abort });

	promise
		.then(() => _patch(id, { loaded: file.size, status: 'success' }, true))
		.catch((e: unknown) => {
			const isCancel =
				(e instanceof ApiError && e.status === 0) ||
				(e instanceof Error && e.name === 'AbortError');
			const msg = e instanceof ApiError ? e.message : ((e as Error)?.message ?? '업로드 실패');
			_patch(id, { status: isCancel ? 'canceled' : 'error', error: msg }, true);
		});

	return id;
}

function _patch(id: string, patch: Partial<UploadJob>, terminal = false) {
	jobs.update((arr) => arr.map((j) => (j.id === id ? { ...j, ...patch } : j)));
	if (terminal) {
		const j = get(jobs).find((x) => x.id === id);
		j?.onComplete?.(j);
	}
}

function cancel(id: string) {
	const j = get(jobs).find((x) => x.id === id);
	j?.abort?.();
}

function remove(id: string) {
	jobs.update((arr) => arr.filter((j) => j.id !== id));
}

export const uploadQueue = { subscribe: jobs.subscribe, enqueue, cancel, remove };
