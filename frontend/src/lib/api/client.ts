import { env } from '$env/dynamic/public';

// 브라우저에서 직접 접근하는 Backend 주소
// PUBLIC_API_BASE 는 docker-compose 또는 .env 에서 런타임으로 주입
export function getBaseUrl(): string {
	if (typeof window !== 'undefined') {
		// 브라우저: PUBLIC_API_BASE 없으면 현재 호스트의 8000 포트로 시도
		return env.PUBLIC_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`;
	}
	// SSR: docker 내부 주소
	return env.PUBLIC_API_BASE || 'http://backend:8000';
}

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

async function request<T>(
	path: string,
	options: RequestInit = {},
	token?: string,
	projectId?: string
): Promise<T> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(options.headers as Record<string, string>)
	};

	if (token) {
		headers['X-Auth-Token'] = token;
	}
	if (projectId) {
		headers['X-Project-Id'] = projectId;
	}

	const res = await fetch(`${getBaseUrl()}${path}`, {
		...options,
		headers,
		signal: options.signal ?? AbortSignal.timeout(30_000),
	});

	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = await res.json();
			detail = body?.detail || JSON.stringify(body);
		} catch {
			detail = await res.text().catch(() => res.statusText);
		}
		throw new ApiError(res.status, detail);
	}

	if (res.status === 204) return undefined as T;
	return res.json();
}

// 브라우저 세션 내 인메모리 캐시 (SWR용)
export const memoryCache = new Map<string, { data: unknown; timestamp: number }>();

export const api = {
	get: <T>(
		path: string,
		token?: string,
		projectId?: string,
		opts?: { refresh?: boolean; signal?: AbortSignal }
	) => {
		const url = opts?.refresh ? `${path}${path.includes('?') ? '&' : '?'}refresh=true` : path;
		const signal = opts?.signal
			? AbortSignal.any([opts.signal, AbortSignal.timeout(30_000)])
			: undefined;
		return request<T>(url, { method: 'GET', signal }, token, projectId);
	},
	post: <T>(path: string, body: unknown, token?: string, projectId?: string) =>
		request<T>(path, { method: 'POST', body: JSON.stringify(body) }, token, projectId),
	put: <T>(path: string, body: unknown, token?: string, projectId?: string) =>
		request<T>(path, { method: 'PUT', body: JSON.stringify(body) }, token, projectId),
	patch: <T>(path: string, body: unknown, token?: string, projectId?: string) =>
		request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }, token, projectId),
	delete: <T>(path: string, token?: string, projectId?: string) =>
		request<T>(path, { method: 'DELETE' }, token, projectId),

	upload: async <T>(path: string, formData: FormData, token?: string, projectId?: string): Promise<T> => {
		const headers: Record<string, string> = {};
		if (token) headers['X-Auth-Token'] = token;
		if (projectId) headers['X-Project-Id'] = projectId;
		const res = await fetch(`${getBaseUrl()}${path}`, {
			method: 'POST',
			headers,
			body: formData,
			signal: AbortSignal.timeout(300_000),
		});
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				detail = body?.detail || JSON.stringify(body);
			} catch {
				detail = await res.text().catch(() => res.statusText);
			}
			throw new ApiError(res.status, detail);
		}
		if (res.status === 204) return undefined as T;
		return res.json();
	},

	uploadWithProgress: <T>(
		path: string,
		formData: FormData,
		onProgress: (event: { loaded: number; total: number }) => void,
		token?: string,
		projectId?: string,
	): { promise: Promise<T>; abort: () => void } => {
		const xhr = new XMLHttpRequest();
		const promise = new Promise<T>((resolve, reject) => {
			xhr.open('POST', `${getBaseUrl()}${path}`);
			if (token) xhr.setRequestHeader('X-Auth-Token', token);
			if (projectId) xhr.setRequestHeader('X-Project-Id', projectId);
			xhr.timeout = 0; // 타임아웃 없음 (서버 측에서 관리)

			xhr.upload.onprogress = (e) => {
				if (e.lengthComputable) {
					onProgress({ loaded: e.loaded, total: e.total });
				}
			};
			xhr.onload = () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					if (xhr.status === 204) { resolve(undefined as T); return; }
					try { resolve(JSON.parse(xhr.responseText)); }
					catch { resolve(undefined as T); }
				} else {
					let detail = xhr.statusText;
					try { detail = JSON.parse(xhr.responseText)?.detail || detail; } catch { /* empty */ }
					reject(new ApiError(xhr.status, detail));
				}
			};
			xhr.onerror = () => reject(new Error('네트워크 오류가 발생했습니다'));
			xhr.onabort = () => reject(new ApiError(0, '업로드가 취소되었습니다'));
			xhr.send(formData);
		});
		return { promise, abort: () => xhr.abort() };
	},

	putWithProgress: <T>(
		path: string,
		blob: Blob,
		contentType: string,
		onProgress: (event: { loaded: number; total: number }) => void,
		token?: string,
		projectId?: string,
	): { promise: Promise<T>; abort: () => void } => {
		const xhr = new XMLHttpRequest();
		const promise = new Promise<T>((resolve, reject) => {
			xhr.open('PUT', `${getBaseUrl()}${path}`);
			if (token) xhr.setRequestHeader('X-Auth-Token', token);
			if (projectId) xhr.setRequestHeader('X-Project-Id', projectId);
			xhr.setRequestHeader('Content-Type', contentType || 'application/octet-stream');
			xhr.timeout = 0;

			xhr.upload.onprogress = (e) => {
				if (e.lengthComputable) onProgress({ loaded: e.loaded, total: e.total });
			};
			xhr.onload = () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					if (xhr.status === 204) { resolve(undefined as T); return; }
					try { resolve(JSON.parse(xhr.responseText)); }
					catch { resolve(undefined as T); }
				} else {
					let detail = xhr.statusText;
					try { detail = JSON.parse(xhr.responseText)?.detail || detail; } catch { /* empty */ }
					reject(new ApiError(xhr.status, detail));
				}
			};
			xhr.onerror = () => reject(new Error('네트워크 오류가 발생했습니다'));
			xhr.onabort = () => reject(new ApiError(0, '업로드가 취소되었습니다'));
			xhr.send(blob);
		});
		return { promise, abort: () => xhr.abort() };
	},

	/** 절대 URL에 PUT (RGW presigned 등). 인증 헤더·Content-Type 미부착, ETag 반환.
	 * presigned upload_part는 X-Amz-SignedHeaders=host 만 서명하므로 Content-Type을 보내면
	 * RGW가 서명 불일치로 403을 반환할 수 있다. 호출자는 MIME 타입 없는 Blob을 전달해야 한다. */
	putAbsoluteWithProgress(
		url: string,
		body: Blob,
		onProgress: (p: { loaded: number; total: number }) => void,
		signal?: AbortSignal,
	): Promise<{ etag: string }> {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			xhr.open('PUT', url, true);
			xhr.upload.onprogress = (e) => {
				if (e.lengthComputable) onProgress({ loaded: e.loaded, total: e.total });
			};
			xhr.onload = () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					resolve({ etag: xhr.getResponseHeader('ETag') || '' });
				} else {
					reject(new ApiError(xhr.status, `PUT failed: ${xhr.status}`));
				}
			};
			xhr.onerror = () => reject(new ApiError(0, '네트워크 오류가 발생했습니다'));
			xhr.onabort = () => reject(new ApiError(0, '업로드가 취소되었습니다'));
			signal?.addEventListener('abort', () => xhr.abort());
			xhr.send(body);
		});
	},

	downloadBlob: async (path: string, token?: string, projectId?: string): Promise<{ blob: Blob; filename: string }> => {
		const headers: Record<string, string> = { 'Content-Type': 'application/json' };
		if (token) headers['X-Auth-Token'] = token;
		if (projectId) headers['X-Project-Id'] = projectId;
		const res = await fetch(`${getBaseUrl()}${path}`, {
			method: 'GET',
			headers,
			signal: AbortSignal.timeout(300_000),
		});
		if (!res.ok) {
			let detail = res.statusText;
			try { detail = (await res.json())?.detail || detail; } catch { /* empty */ }
			throw new ApiError(res.status, detail);
		}
		const disposition = res.headers.get('Content-Disposition') || '';
		const match = disposition.match(/filename="?([^"]+)"?/);
		const filename = match ? decodeURIComponent(match[1]) : 'download';
		const blob = await res.blob();
		return { blob, filename };
	},

	/**
	 * SSE (Server-Sent Events) 요청
	 * @param path API 경로
	 * @param body 요청 본문
	 * @param token 인증 토큰
	 * @param projectId 프로젝트 ID
	 * @param onMessage 각 메시지 수신 시 호출되는 콜백
	 * @param onError 에러 발생 시 호출되는 콜백
	 */
	postSse: <T>(
		path: string,
		body: unknown,
		token?: string,
		projectId?: string,
		onMessage?: (data: T) => void,
		onError?: (error: Error) => void
	): void => {
		const baseUrl = getBaseUrl();
		const url = new URL(`${baseUrl}${path}`);

		// POST 요청을 SSE로 처리하기 위해 fetch 사용 후 EventSource로 전환
		// 하지만 EventSource는 POST를 지원하지 않으므로, fetch로 SSE 스트림을 처리
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			'Accept': 'text/event-stream'
		};
		if (token) headers['X-Auth-Token'] = token;
		if (projectId) headers['X-Project-Id'] = projectId;

		// fetch로 POST 요청 후 스트림 처리
		fetch(url, {
			method: 'POST',
			headers,
			body: JSON.stringify(body)
		}).then(async (response) => {
			if (!response.ok) {
				const text = await response.text();
				throw new ApiError(response.status, text || response.statusText);
			}

			const reader = response.body?.getReader();
			if (!reader) throw new Error('No response body');

			const decoder = new TextDecoder();
			let buffer = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';

				for (const line of lines) {
					if (line.startsWith('data: ')) {
						try {
							const data = JSON.parse(line.slice(6)) as T;
							onMessage?.(data);
						} catch {
							// JSON 파싱 실패 시 무시
						}
					}
				}
			}
		}).catch((err) => {
			onError?.(err);
		});
	}
};
