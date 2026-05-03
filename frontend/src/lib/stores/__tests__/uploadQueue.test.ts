import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { get } from 'svelte/store';

vi.stubGlobal('crypto', { randomUUID: vi.fn(() => 'job-uuid') });

vi.mock('$lib/api/client', () => {
	class ApiError extends Error {
		status: number;
		constructor(status: number, message: string) {
			super(message);
			this.status = status;
		}
	}
	return {
		api: { putWithProgress: vi.fn() },
		ApiError,
	};
});

describe('uploadQueue', () => {
	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
		(crypto.randomUUID as Mock).mockReturnValue('job-uuid');
	});

	function makeProgress() {
		let resolvePromise: () => void;
		let rejectPromise: (e: Error) => void;
		const abortFn = vi.fn();
		const promise = new Promise<void>((res, rej) => {
			resolvePromise = res;
			rejectPromise = rej;
		});
		return { promise, abort: abortFn, resolvePromise: resolvePromise!, rejectPromise: rejectPromise! };
	}

	it('enqueue() 호출 시 job이 uploading 상태로 추가됨', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['content'], 'test.txt', { type: 'text/plain' });
		uploadQueue.enqueue(file, { containerName: 'my-bucket' });

		const jobs = get(uploadQueue);
		expect(jobs).toHaveLength(1);
		expect(jobs[0].status).toBe('uploading');
		expect(jobs[0].name).toBe('test.txt');
		expect(jobs[0].containerName).toBe('my-bucket');
	});

	it('putWithProgress를 올바른 경로로 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'report.csv', { type: 'text/csv' });
		uploadQueue.enqueue(file, { containerName: 'bucket', token: 'tok', projectId: 'p' });

		expect(api.putWithProgress).toHaveBeenCalledWith(
			'/api/object-storage/bucket/objects/report.csv',
			file,
			'text/csv',
			expect.any(Function),
			'tok',
			'p'
		);
	});

	it('promise 성공 시 status가 success로 변경', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort, resolvePromise } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c' });
		resolvePromise();
		await promise.catch(() => {});
		await new Promise((r) => setTimeout(r, 0));

		expect(get(uploadQueue)[0].status).toBe('success');
	});

	it('promise 성공 시 onComplete 콜백 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort, resolvePromise } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const onComplete = vi.fn();
		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c', onComplete });
		resolvePromise();
		await new Promise((r) => setTimeout(r, 0));

		expect(onComplete).toHaveBeenCalledOnce();
		expect(onComplete.mock.calls[0][0].status).toBe('success');
	});

	it('AbortError(status=0) 시 status가 canceled로 변경', async () => {
		const { api, ApiError } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort, rejectPromise } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c' });
		rejectPromise(new ApiError(0, '취소'));
		await new Promise((r) => setTimeout(r, 0));

		expect(get(uploadQueue)[0].status).toBe('canceled');
	});

	it('일반 오류 시 status가 error로 변경', async () => {
		const { api, ApiError } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort, rejectPromise } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c' });
		rejectPromise(new ApiError(500, '서버 오류'));
		await new Promise((r) => setTimeout(r, 0));

		const job = get(uploadQueue)[0];
		expect(job.status).toBe('error');
		expect(job.error).toBe('서버 오류');
	});

	it('cancel(id)로 abort 함수 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'file.txt');
		const id = uploadQueue.enqueue(file, { containerName: 'c' });
		uploadQueue.cancel(id);

		expect(abort).toHaveBeenCalledOnce();
	});

	it('remove(id)로 큐에서 제거', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'file.txt');
		const id = uploadQueue.enqueue(file, { containerName: 'c' });
		expect(get(uploadQueue)).toHaveLength(1);
		uploadQueue.remove(id);
		expect(get(uploadQueue)).toHaveLength(0);
	});

	it('prefix가 있으면 경로에 포함 (각 segment 별도 인코딩)', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');
		const { promise, abort } = makeProgress();
		vi.mocked(api.putWithProgress).mockReturnValue({ promise, abort });

		const file = new File(['x'], 'notes.md');
		uploadQueue.enqueue(file, { containerName: 'bucket', prefix: 'docs/' });

		// 경로는 각 segment를 encodeURIComponent 후 /로 재결합 → docs/notes.md (슬래시 보존)
		const [callPath] = vi.mocked(api.putWithProgress).mock.calls[0];
		expect(callPath).toContain('/docs/notes.md');
		expect(callPath).toContain('/api/object-storage/bucket/objects/');
	});
});
