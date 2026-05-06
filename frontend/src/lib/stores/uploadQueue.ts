import { get, writable } from 'svelte/store';
import { ApiError, api, getBaseUrl } from '$lib/api/client';

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

const jobs = writable<UploadJob[]>([]);

const MAX_CONCURRENT_PARTS = 4;

/** 최대 동시 실행 수를 제한하는 세마포어. */
class Semaphore {
	private queue: (() => void)[] = [];
	private running = 0;
	constructor(private limit: number) {}

	async acquire(): Promise<void> {
		if (this.running < this.limit) {
			this.running++;
			return;
		}
		await new Promise<void>((res) => this.queue.push(res));
		this.running++;
	}

	release(): void {
		this.running--;
		const next = this.queue.shift();
		if (next) next();
	}
}

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
	const objectName = (params.prefix ?? '') + file.name;

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

	const abortController = new AbortController();
	_patch(id, { abort: () => abortController.abort() });

	_runMultipartUpload(id, file, objectName, params, abortController.signal);

	return id;
}

async function _runMultipartUpload(
	id: string,
	file: File,
	objectName: string,
	params: {
		containerName: string;
		token?: string;
		projectId?: string;
	},
	signal: AbortSignal
): Promise<void> {
	let transactionId: string | undefined;

	try {
		// 1. 업로드 초기화
		const initResp = await api.post<{
			transaction_id: string;
			quarantine_bucket: string;
			upload_id: string;
			parts: Array<{ part_number: number; url: string }>;
			part_size: number;
		}>(
			`/api/object-storage/${encodeURIComponent(params.containerName)}/upload/init`,
			{
				object_name: objectName,
				content_type: file.type || 'application/octet-stream',
				size: file.size
			},
			params.token,
			params.projectId
		);

		if (signal.aborted) throw new ApiError(0, '업로드가 취소되었습니다');

		transactionId = initResp.transaction_id;
		const { parts, part_size } = initResp;

		// 2. 각 part 병렬 업로드 (최대 4개 동시)
		const semaphore = new Semaphore(MAX_CONCURRENT_PARTS);
		const aggLoaded = new Map<number, number>();
		const completedParts: Array<{ part_number: number; etag: string }> = [];

		function reportProgress() {
			let total = 0;
			for (const v of aggLoaded.values()) total += v;
			_patch(id, { loaded: total });
		}

		const partPromises = parts.map(async ({ part_number, url }) => {
			await semaphore.acquire();
			if (signal.aborted) {
				semaphore.release();
				throw new ApiError(0, '업로드가 취소되었습니다');
			}
			try {
				const start = (part_number - 1) * part_size;
				const end = Math.min(start + part_size, file.size);
				// MIME 타입 없는 Blob → XHR이 Content-Type 헤더를 전송하지 않음
				// (RGW presigned URL의 X-Amz-SignedHeaders=host 서명 검증 통과용)
				const blob = new Blob([file.slice(start, end)]);

				const { etag } = await api.putAbsoluteWithProgress(
					url,
					blob,
					(e) => {
						aggLoaded.set(part_number, e.loaded);
						reportProgress();
					},
					signal
				);
				completedParts.push({ part_number, etag });
			} finally {
				semaphore.release();
			}
		});

		await Promise.all(partPromises);

		if (signal.aborted) throw new ApiError(0, '업로드가 취소되었습니다');

		// 3. 업로드 완료
		await api.post(
			`/api/object-storage/${encodeURIComponent(params.containerName)}/upload/complete`,
			{ transaction_id: transactionId, parts: completedParts },
			params.token,
			params.projectId
		);

		_patch(id, { loaded: file.size, status: 'success' }, true);
	} catch (e) {
		// abort 호출 시 서버 측 정리
		if (transactionId) {
			api
				.post(
					`/api/object-storage/${encodeURIComponent(params.containerName)}/upload/abort`,
					{ transaction_id: transactionId },
					params.token,
					params.projectId
				)
				.catch(() => {});
		}

		const isCancel =
			(e instanceof ApiError && e.status === 0) ||
			(e instanceof Error && e.name === 'AbortError');
		const msg = e instanceof ApiError ? e.message : ((e as Error)?.message ?? '업로드 실패');
		_patch(id, { status: isCancel ? 'canceled' : 'error', error: msg }, true);
	}
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
