import { get, writable } from 'svelte/store';
import { ApiError, api } from '$lib/api/client';

export type UploadKind = 'object' | 'image';

export interface UploadJob {
	id: string;
	name: string;
	kind: UploadKind;
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
		/** object-storage 업로드 시 사용. image 업로드 시에는 endpoint를 직접 지정. */
		containerName?: string;
		prefix?: string;
		/** image 업로드 시 '/api/v1/images' 등 엔드포인트를 직접 지정. */
		endpoint?: string;
		/** 추가 FormData 필드 (이미지 name, disk_format 등). */
		extraFields?: Record<string, string>;
		kind?: UploadKind;
		token?: string;
		projectId?: string;
		onComplete?: (job: UploadJob) => void;
	}
): string {
	const id = crypto.randomUUID();
	const kind: UploadKind = params.kind ?? 'object';

	const job: UploadJob = {
		id,
		name: file.name,
		kind,
		containerName: params.containerName ?? '',
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

	let uploadUrl: string;
	if (params.endpoint) {
		uploadUrl = params.endpoint;
		if (params.extraFields) {
			for (const [k, v] of Object.entries(params.extraFields)) {
				formData.append(k, v);
			}
		}
	} else {
		uploadUrl = `/api/v1/object-storage/${encodeURIComponent(params.containerName ?? '')}/upload`;
		if (params.prefix) formData.append('prefix', params.prefix);
	}

	const { promise, abort } = api.uploadWithProgress<UploadResponse>(
		uploadUrl,
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
