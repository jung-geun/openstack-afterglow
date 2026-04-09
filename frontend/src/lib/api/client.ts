import { env } from '$env/dynamic/public';

// 브라우저에서 직접 접근하는 Backend 주소
// PUBLIC_API_BASE 는 docker-compose 또는 .env 에서 런타임으로 주입
function getBaseUrl(): string {
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

	const res = await fetch(`${getBaseUrl()}${path}`, { ...options, headers });

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
	get: <T>(path: string, token?: string, projectId?: string, opts?: { refresh?: boolean }) => {
		const url = opts?.refresh ? `${path}${path.includes('?') ? '&' : '?'}refresh=true` : path;
		return request<T>(url, { method: 'GET' }, token, projectId);
	},
	post: <T>(path: string, body: unknown, token?: string, projectId?: string) =>
		request<T>(path, { method: 'POST', body: JSON.stringify(body) }, token, projectId),
	put: <T>(path: string, body: unknown, token?: string, projectId?: string) =>
		request<T>(path, { method: 'PUT', body: JSON.stringify(body) }, token, projectId),
	patch: <T>(path: string, body: unknown, token?: string, projectId?: string) =>
		request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }, token, projectId),
	delete: <T>(path: string, token?: string, projectId?: string) =>
		request<T>(path, { method: 'DELETE' }, token, projectId),

	/**
	 * SSE (Server-Sent Events) 요청
	 * @param path API 경로
	 * @param body 요청 본문
	 * @param token 인증 토큰
	 * @param projectId 프로젝트 ID
	 * @param onMessage 각 메시지 수신 시 호출되는 콜백
	 * @param onError 에러 발생 시 호출되는 콜백
	 * @returns EventSource 인스턴스
	 */
	postSse: <T>(
		path: string,
		body: unknown,
		token?: string,
		projectId?: string,
		onMessage?: (data: T) => void,
		onError?: (error: Error) => void
	): EventSource => {
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

		// EventSource 호환을 위해 더미 객체 반환
		return new EventSource(url.href);
	}
};
