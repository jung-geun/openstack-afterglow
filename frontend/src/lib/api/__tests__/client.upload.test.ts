import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$env/dynamic/public', () => ({
	env: { PUBLIC_API_BASE: 'http://localhost:8000' },
}));

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// XHR mock — 테스트가 직접 이벤트를 트리거
let lastXhr: MockXhr;
class MockXhr {
	status = 200;
	responseText = '{}';
	statusText = 'OK';
	timeout = 0;
	upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
		onprogress: null,
	};
	onload: (() => void) | null = null;
	onerror: (() => void) | null = null;
	onabort: (() => void) | null = null;
	_headers: Record<string, string> = {};
	_method = '';
	_url = '';
	_body: unknown = null;

	open(method: string, url: string) {
		this._method = method;
		this._url = url;
	}
	setRequestHeader(k: string, v: string) {
		this._headers[k] = v;
	}
	send(body: unknown) {
		this._body = body;
	}
	abort() {
		this.onabort?.();
	}
	constructor() {
		// eslint-disable-next-line @typescript-eslint/no-this-alias
		lastXhr = this;
	}
}
vi.stubGlobal('XMLHttpRequest', MockXhr);

describe('api.upload', () => {
	beforeEach(() => {
		mockFetch.mockReset();
		vi.resetModules();
	});

	it('FormData POST에 올바른 헤더 설정', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ id: 'obj-1' }),
		});

		const { api } = await import('../client');
		const formData = new FormData();
		const result = await api.upload('/api/upload', formData, 'my-token', 'proj-1');

		const [url, opts] = mockFetch.mock.calls[0];
		expect(url).toContain('/api/upload');
		expect(opts.method).toBe('POST');
		expect(opts.headers['X-Auth-Token']).toBe('my-token');
		expect(opts.headers['X-Project-Id']).toBe('proj-1');
		expect(opts.headers['Content-Type']).toBeUndefined();
		expect(result).toEqual({ id: 'obj-1' });
	});

	it('204 응답 시 undefined 반환', async () => {
		mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
		const { api } = await import('../client');
		const result = await api.upload('/api/upload', new FormData());
		expect(result).toBeUndefined();
	});

	it('오류 응답 시 ApiError 반환', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 413,
			statusText: 'Too Large',
			json: async () => ({ detail: '파일이 너무 큽니다' }),
		});
		const { api, ApiError } = await import('../client');
		await expect(api.upload('/api/upload', new FormData())).rejects.toBeInstanceOf(ApiError);
	});
});

describe('api.uploadWithProgress', () => {
	beforeEach(() => {
		vi.resetModules();
	});

	it('XHR에 올바른 헤더 설정', async () => {
		const { api } = await import('../client');
		api.uploadWithProgress('/api/upload', new FormData(), vi.fn(), 'tok', 'my-proj');

		expect(lastXhr._headers['X-Auth-Token']).toBe('tok');
		expect(lastXhr._headers['X-Project-Id']).toBe('my-proj');
		expect(lastXhr._method).toBe('POST');
	});

	it('onload 성공 시 JSON 파싱 결과 반환', async () => {
		const { api } = await import('../client');
		// uploadWithProgress 호출 후에 lastXhr 설정 (XHR 인스턴스가 생성된 뒤)
		const { promise } = api.uploadWithProgress('/api/upload', new FormData(), vi.fn());
		lastXhr.status = 200;
		lastXhr.responseText = '{"id":"obj-1"}';
		lastXhr.onload?.();

		const result = await promise;
		expect(result).toEqual({ id: 'obj-1' });
	});

	it('204 응답 시 undefined 반환', async () => {
		const { api } = await import('../client');
		const { promise } = api.uploadWithProgress('/api/upload', new FormData(), vi.fn());
		lastXhr.status = 204;
		lastXhr.onload?.();

		expect(await promise).toBeUndefined();
	});

	it('progress 이벤트 콜백 호출', async () => {
		const { api } = await import('../client');
		const onProgress = vi.fn();
		api.uploadWithProgress('/api/upload', new FormData(), onProgress);

		lastXhr.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
		expect(onProgress).toHaveBeenCalledWith({ loaded: 50, total: 100 });
	});

	it('lengthComputable=false면 onProgress 호출 안 함', async () => {
		const { api } = await import('../client');
		const onProgress = vi.fn();
		api.uploadWithProgress('/api/upload', new FormData(), onProgress);

		lastXhr.upload.onprogress?.({ lengthComputable: false, loaded: 0, total: 0 });
		expect(onProgress).not.toHaveBeenCalled();
	});

	it('abort()로 ApiError(0) reject', async () => {
		const { api, ApiError } = await import('../client');
		const { promise, abort } = api.uploadWithProgress('/api/upload', new FormData(), vi.fn());
		abort();
		await expect(promise).rejects.toBeInstanceOf(ApiError);
		await expect(promise).rejects.toMatchObject({ status: 0 });
	});

	it('4xx onload 시 ApiError reject', async () => {
		const { api, ApiError } = await import('../client');
		const { promise } = api.uploadWithProgress('/api/upload', new FormData(), vi.fn());
		lastXhr.status = 400;
		lastXhr.statusText = 'Bad Request';
		lastXhr.responseText = '{"detail":"잘못된 요청"}';
		lastXhr.onload?.();
		await expect(promise).rejects.toBeInstanceOf(ApiError);
	});

	it('onerror 시 네트워크 오류 reject', async () => {
		const { api } = await import('../client');
		const { promise } = api.uploadWithProgress('/api/upload', new FormData(), vi.fn());
		lastXhr.onerror?.();
		await expect(promise).rejects.toThrow('네트워크 오류');
	});
});

describe('api.putWithProgress', () => {
	beforeEach(() => {
		vi.resetModules();
	});

	it('PUT 메서드로 blob 전송', async () => {
		const { api } = await import('../client');
		const blob = new Blob(['data'], { type: 'text/plain' });
		api.putWithProgress('/api/upload', blob, 'text/plain', vi.fn(), 'tok', 'proj');

		expect(lastXhr._method).toBe('PUT');
		expect(lastXhr._headers['Content-Type']).toBe('text/plain');
		expect(lastXhr._headers['X-Auth-Token']).toBe('tok');
		expect(lastXhr._body).toBe(blob);
	});

	it('성공 시 JSON 파싱', async () => {
		const { api } = await import('../client');
		const blob = new Blob(['data']);
		const { promise } = api.putWithProgress('/api/upload', blob, 'application/octet-stream', vi.fn());
		lastXhr.status = 200;
		lastXhr.responseText = '{"etag":"abc"}';
		lastXhr.onload?.();

		expect(await promise).toEqual({ etag: 'abc' });
	});

	it('abort() 동작', async () => {
		const { api, ApiError } = await import('../client');
		const blob = new Blob(['data']);
		const { promise, abort } = api.putWithProgress('/api/upload', blob, 'application/octet-stream', vi.fn());
		abort();
		await expect(promise).rejects.toBeInstanceOf(ApiError);
	});

	it('contentType 없으면 application/octet-stream 기본값', async () => {
		const { api } = await import('../client');
		const blob = new Blob(['data']);
		api.putWithProgress('/api/upload', blob, '', vi.fn());
		expect(lastXhr._headers['Content-Type']).toBe('application/octet-stream');
	});
});

describe('api.downloadBlob', () => {
	beforeEach(() => {
		mockFetch.mockReset();
		vi.resetModules();
	});

	it('Content-Disposition에서 filename 파싱', async () => {
		const blob = new Blob(['file content'], { type: 'text/plain' });
		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			headers: new Headers({ 'Content-Disposition': 'attachment; filename="report.pdf"' }),
			blob: async () => blob,
		});

		const { api } = await import('../client');
		const result = await api.downloadBlob('/api/download');
		expect(result.filename).toBe('report.pdf');
		expect(result.blob).toBe(blob);
	});

	it('Content-Disposition 없으면 "download" 기본값', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			headers: new Headers(),
			blob: async () => new Blob(['x']),
		});

		const { api } = await import('../client');
		const result = await api.downloadBlob('/api/download');
		expect(result.filename).toBe('download');
	});

	it('인증 헤더 전달', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			headers: new Headers(),
			blob: async () => new Blob(),
		});

		const { api } = await import('../client');
		await api.downloadBlob('/api/download', 'tok', 'proj-1');

		const [, opts] = mockFetch.mock.calls[0];
		expect(opts.headers['X-Auth-Token']).toBe('tok');
		expect(opts.headers['X-Project-Id']).toBe('proj-1');
	});

	it('오류 응답 시 ApiError 반환', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 403,
			statusText: 'Forbidden',
			json: async () => ({ detail: '권한 없음' }),
		});

		const { api, ApiError } = await import('../client');
		await expect(api.downloadBlob('/api/download')).rejects.toBeInstanceOf(ApiError);
	});
});

describe('api.postSse', () => {
	beforeEach(() => {
		mockFetch.mockReset();
		vi.resetModules();
	});

	function makeStreamResponse(chunks: string[]) {
		const encoder = new TextEncoder();
		let index = 0;
		const reader = {
			read: vi.fn(async () => {
				if (index < chunks.length) {
					return { done: false, value: encoder.encode(chunks[index++]) };
				}
				return { done: true, value: undefined };
			}),
		};
		return {
			ok: true,
			status: 200,
			body: { getReader: () => reader },
		};
	}

	it('data: 라인을 파싱해 onMessage 콜백 호출', async () => {
		const onMessage = vi.fn();
		mockFetch.mockResolvedValueOnce(
			makeStreamResponse(['data: {"status":"running"}\n', 'data: {"status":"done"}\n', ''])
		);

		const { api } = await import('../client');
		api.postSse('/api/sse', { cmd: 'run' }, 'tok', 'proj', onMessage);

		// 비동기 스트림 처리 대기
		await new Promise((r) => setTimeout(r, 10));
		expect(onMessage).toHaveBeenCalledTimes(2);
		expect(onMessage.mock.calls[0][0]).toEqual({ status: 'running' });
		expect(onMessage.mock.calls[1][0]).toEqual({ status: 'done' });
	});

	it('JSON 파싱 실패는 조용히 무시', async () => {
		const onMessage = vi.fn();
		mockFetch.mockResolvedValueOnce(makeStreamResponse(['data: not-json\n', '']));

		const { api } = await import('../client');
		api.postSse('/api/sse', {}, undefined, undefined, onMessage);
		await new Promise((r) => setTimeout(r, 10));
		expect(onMessage).not.toHaveBeenCalled();
	});

	it('fetch 오류 시 onError 콜백 호출', async () => {
		const onError = vi.fn();
		mockFetch.mockRejectedValueOnce(new Error('Network failure'));

		const { api } = await import('../client');
		api.postSse('/api/sse', {}, undefined, undefined, undefined, onError);
		await new Promise((r) => setTimeout(r, 10));
		expect(onError).toHaveBeenCalledOnce();
	});

	it('인증 헤더 전달', async () => {
		mockFetch.mockResolvedValueOnce(makeStreamResponse(['']));

		const { api } = await import('../client');
		api.postSse('/api/sse', { body: true }, 'my-tok', 'my-proj');
		await new Promise((r) => setTimeout(r, 10));

		const [, opts] = mockFetch.mock.calls[0];
		expect(opts.headers['X-Auth-Token']).toBe('my-tok');
		expect(opts.headers['X-Project-Id']).toBe('my-proj');
		expect(opts.headers['Accept']).toBe('text/event-stream');
	});
});

describe('getBaseUrl', () => {
	beforeEach(() => {
		vi.resetModules();
	});

	it('PUBLIC_API_BASE가 설정되어 있으면 그것을 반환', async () => {
		vi.mock('$env/dynamic/public', () => ({
			env: { PUBLIC_API_BASE: 'http://api.example.com' },
		}));
		const { getBaseUrl } = await import('../client');
		expect(getBaseUrl()).toBe('http://api.example.com');
	});
});

describe('memoryCache', () => {
	it('Map 인스턴스 export', async () => {
		const { memoryCache } = await import('../client');
		expect(memoryCache).toBeInstanceOf(Map);
	});
});
