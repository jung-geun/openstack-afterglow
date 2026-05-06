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
		api: {
			post: vi.fn(),
			putAbsoluteWithProgress: vi.fn()
		},
		ApiError,
		getBaseUrl: () => ''
	};
});

const INIT_RESP = {
	transaction_id: 'tx-1',
	quarantine_bucket: 'c-quarantine',
	upload_id: 'up-1',
	parts: [{ part_number: 1, url: 'https://rgw/p1' }],
	part_size: 1024
};

describe('uploadQueue', () => {
	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
		(crypto.randomUUID as Mock).mockReturnValue('job-uuid');
	});

	it('enqueue() 호출 시 job이 uploading 상태로 추가됨', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['content'], 'test.txt', { type: 'text/plain' });
		uploadQueue.enqueue(file, { containerName: 'my-bucket' });

		const jobs = get(uploadQueue);
		expect(jobs).toHaveLength(1);
		expect(jobs[0].status).toBe('uploading');
		expect(jobs[0].name).toBe('test.txt');
		expect(jobs[0].containerName).toBe('my-bucket');
	});

	it('업로드 초기화 시 올바른 경로로 POST 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['x'], 'report.csv', { type: 'text/csv' });
		uploadQueue.enqueue(file, { containerName: 'bucket', token: 'tok', projectId: 'p' });

		await new Promise((r) => setTimeout(r, 0));

		expect(api.post).toHaveBeenCalledWith(
			'/api/object-storage/bucket/upload/init',
			{ object_name: 'report.csv', content_type: 'text/csv', size: 1 },
			'tok',
			'p'
		);
	});

	it('init 완료 후 presigned URL로 PUT 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['x'], 'file.txt', { type: 'text/plain' });
		uploadQueue.enqueue(file, { containerName: 'c' });
		await new Promise((r) => setTimeout(r, 20));

		expect(api.putAbsoluteWithProgress).toHaveBeenCalledWith(
			'https://rgw/p1',
			expect.any(Blob),
			'text/plain',
			expect.any(Function),
			expect.any(AbortSignal)
		);
	});

	it('모든 part 완료 후 complete 호출 → status success', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c' });
		await new Promise((r) => setTimeout(r, 20));

		expect(get(uploadQueue)[0].status).toBe('success');
		const completeCalls = vi.mocked(api.post).mock.calls.filter((c) =>
			c[0].includes('/upload/complete')
		);
		expect(completeCalls).toHaveLength(1);
		expect(completeCalls[0][1]).toMatchObject({
			transaction_id: 'tx-1',
			parts: [{ part_number: 1, etag: '"abc"' }]
		});
	});

	it('promise 성공 시 onComplete 콜백 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const onComplete = vi.fn();
		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c', onComplete });
		await new Promise((r) => setTimeout(r, 20));

		expect(onComplete).toHaveBeenCalledOnce();
		expect(onComplete.mock.calls[0][0].status).toBe('success');
	});

	it('init 실패(status=0) 시 status가 canceled로 변경', async () => {
		const { api, ApiError } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockRejectedValueOnce(new ApiError(0, '취소'));

		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c' });
		await new Promise((r) => setTimeout(r, 20));

		expect(get(uploadQueue)[0].status).toBe('canceled');
	});

	it('init 실패(status=500) 시 status가 error로 변경', async () => {
		const { api, ApiError } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockRejectedValueOnce(new ApiError(500, '서버 오류'));

		const file = new File(['x'], 'file.txt');
		uploadQueue.enqueue(file, { containerName: 'c' });
		await new Promise((r) => setTimeout(r, 20));

		const job = get(uploadQueue)[0];
		expect(job.status).toBe('error');
		expect(job.error).toBe('서버 오류');
	});

	it('cancel(id)로 abort 호출 → status가 canceled로 변경', async () => {
		const { api, ApiError } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		// init 성공, PUT 단계에서 AbortError 발생
		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockImplementation(
			(_url, _body, _ct, _onProgress, signal) =>
				new Promise((_res, rej) => {
					signal?.addEventListener('abort', () => rej(new ApiError(0, '취소')));
				})
		);
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['x'], 'file.txt');
		const id = uploadQueue.enqueue(file, { containerName: 'c' });

		// init 완료 후 PUT 진입 시 cancel
		await new Promise((r) => setTimeout(r, 5));
		uploadQueue.cancel(id);
		await new Promise((r) => setTimeout(r, 30));

		expect(get(uploadQueue)[0].status).toBe('canceled');
	});

	it('remove(id)로 큐에서 제거', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['x'], 'file.txt');
		const id = uploadQueue.enqueue(file, { containerName: 'c' });
		expect(get(uploadQueue)).toHaveLength(1);
		uploadQueue.remove(id);
		expect(get(uploadQueue)).toHaveLength(0);
	});

	it('prefix가 있으면 object_name에 포함', async () => {
		const { api } = await import('$lib/api/client');
		const { uploadQueue } = await import('../uploadQueue');

		vi.mocked(api.post).mockResolvedValueOnce(INIT_RESP);
		vi.mocked(api.putAbsoluteWithProgress).mockResolvedValue({ etag: '"abc"' });
		vi.mocked(api.post).mockResolvedValue({});

		const file = new File(['x'], 'notes.md');
		uploadQueue.enqueue(file, { containerName: 'bucket', prefix: 'docs/' });
		await new Promise((r) => setTimeout(r, 20));

		const initCall = vi.mocked(api.post).mock.calls.find((c) => c[0].includes('/upload/init'));
		expect(initCall).toBeDefined();
		expect((initCall![1] as { object_name: string }).object_name).toBe('docs/notes.md');
	});
});
