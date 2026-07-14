import { get } from 'svelte/store';
import { siteConfig } from '$lib/config/site';
import { logoutInProgress } from '$lib/stores/auth';
import { ApiError } from '$lib/api/errors';
import { maybeMockBlob, maybeMockJson, maybeMockK3sStream, symbolNoMatch } from '$lib/mockup/transport';
export { ApiError } from '$lib/api/errors';

function stripTrailingSlash(value: string): string {
	return value.replace(/\/+$/, '');
}

function browserFallbackBaseUrl(): string {
	if (typeof window === 'undefined') return 'http://localhost:8000';
	return `${window.location.protocol}//${window.location.hostname}:8000`;
}

// 브라우저에서 직접 접근하는 Backend 주소
// afterglow.conf의 [app] frontend_base_url/backend_port 조합에서 런타임 주입
export function getBaseUrl(): string {
	const configured = get(siteConfig).runtime.api_base;
	return stripTrailingSlash(configured || browserFallbackBaseUrl());
}

export function getWebSocketUrl(path: string): string {
	const base = new URL(getBaseUrl() || (typeof window === 'undefined' ? 'http://localhost' : window.location.origin));
	base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
	return new URL(path, base).toString();
}


function formatErrorDetail(body: unknown, fallback: string): string {
	if (!body || typeof body !== 'object') return fallback;
	const detail = (body as { detail?: unknown }).detail;
	if (typeof detail === 'string') return detail;
	if (Array.isArray(detail)) {
		return detail
			.map((item) => {
				if (!item || typeof item !== 'object') return String(item);
				const record = item as { loc?: unknown; msg?: unknown };
				const loc = Array.isArray(record.loc) ? record.loc.join('.') : '';
				const msg = typeof record.msg === 'string' ? record.msg : JSON.stringify(item);
				return loc ? `${loc}: ${msg}` : msg;
			})
			.join('; ');
	}
	if (detail && typeof detail === 'object') return JSON.stringify(detail);
	return JSON.stringify(body);
}

// 동시 다수 요청이 401 받을 때 redirect 중복 호출 방지
let _redirectingTo401 = false;
// /api/admin/ 403 핸들러 중복 호출 방지
let _handling403Admin = false;
// 동시 다수 요청이 토큰 refresh를 중복 호출하지 않도록 직렬화
let _refreshPromise: Promise<string | null> | null = null;
let _sessionRevocationInProgress = false;
const AUTH_PUBLIC_PATHS = new Set(['/', '/login', '/auth/gitlab/callback']);


/**
 * /api/admin/ 경로에서 403 응답 시 isSystemAdmin=false 강등 + /dashboard로 이동.
 * one-shot 가드로 무한 루프 방지.
 */
async function handleAdminForbidden(): Promise<void> {
	if (typeof window === 'undefined') return;
	if (_handling403Admin) return;
	if (!window.location.pathname.startsWith('/admin')) return;
	_handling403Admin = true;
	try {
		const [{ auth }, { goto }] = await Promise.all([
			import('$lib/stores/auth'),
			import('$app/navigation'),
		]);
		auth.update((s) => ({ ...s, isSystemAdmin: false }));
		await goto('/dashboard');
	} catch {
		window.location.href = '/dashboard';
	} finally {
		setTimeout(() => { _handling403Admin = false; }, 5000);
	}
}

/**
 * 401 응답 시 인증 상태 정리 + 로그인 페이지(/login)로 자동 redirect.
 */
async function handleUnauthorized(): Promise<void> {
	if (typeof window === 'undefined') return;
	if (_redirectingTo401 || get(logoutInProgress)) return;

	// Mark synchronously before any import or refresh wait so concurrent 401s
	// cannot run a competing clear-and-redirect sequence.
	_redirectingTo401 = true;
	try {
		if (_refreshPromise) {
			const recovered = await _refreshPromise;
			if (recovered) return;
		}

		if (get(logoutInProgress) || AUTH_PUBLIC_PATHS.has(window.location.pathname)) return;
		const [{ clearAuth }, { goto }] = await Promise.all([
			import('$lib/stores/auth'),
			import('$app/navigation'),
		]);
		if (get(logoutInProgress)) return;
		clearAuth();
		await goto('/login', { replaceState: true });
	} catch {
		if (!get(logoutInProgress)) window.location.replace('/login');
	} finally {
		setTimeout(() => { _redirectingTo401 = false; }, 1000);
	}
}

/**
 * refresh 토큰으로 새 access JWT를 발급. 성공하면 새 access token 반환, 실패하면 null.
 * 동시 호출은 하나의 Promise로 합산(coalescing).
 */
/** localStorage에 영속화된 인증 상태를 직접 읽는다 (탭 간 race 대비 최신값 확인용). */
function _readPersistedAuth(): { token?: string; refreshToken?: string; accessExpiresAt?: number } | null {
	try {
		if (typeof localStorage === 'undefined') return null;
		const raw = localStorage.getItem('afterglow_auth');
		return raw ? JSON.parse(raw) : null;
	} catch {
		return null;
	}
}

async function tryRefresh({ allowDuringRevocation = false }: { allowDuringRevocation?: boolean } = {}): Promise<string | null> {
	if (_sessionRevocationInProgress && !allowDuringRevocation) return null;
	if (_refreshPromise) return _refreshPromise;
	_refreshPromise = (async () => {
		try {
			const { get } = await import('svelte/store');
			const { auth, setAuth } = await import('$lib/stores/auth');
			const state = get(auth);

			// 다른 탭이 이미 토큰을 회전시켰을 수 있다 — storage 이벤트 전파보다
			// localStorage 직접 읽기가 항상 최신이므로 여기서 한 번 더 확인한다.
			const persisted = _readPersistedAuth();
			if (persisted?.token && persisted.token !== state.token) {
				setAuth({
					token: persisted.token,
					refreshToken: persisted.refreshToken ?? state.refreshToken,
					accessExpiresAt: persisted.accessExpiresAt ?? null,
				});
				return persisted.token;
			}

			const refreshToken = persisted?.refreshToken ?? state.refreshToken;
			if (!refreshToken) return null;

			const res = await fetch(`${getBaseUrl()}/api/v1/auth/refresh`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ refresh_token: refreshToken }),
				signal: AbortSignal.timeout(15_000),
			});
			if (!res.ok) {
				// refresh 토큰은 1회용(회전 시 폐기) — 동시에 다른 탭이 회전에 성공해
				// 이쪽이 패배한 경우라면 그 탭의 새 토큰을 채택하고 로그아웃하지 않는다.
				const winner = _readPersistedAuth();
				if (winner?.token && winner.token !== state.token) {
					setAuth({
						token: winner.token,
						refreshToken: winner.refreshToken ?? null,
						accessExpiresAt: winner.accessExpiresAt ?? null,
					});
					return winner.token;
				}
				return null;
			}

			const data = await res.json();

			const refreshedToken = data.token as string;
			if (get(auth).token !== state.token) return null;
			setAuth({
				token: refreshedToken,
				refreshToken: data.refresh_token ?? refreshToken,
				accessExpiresAt: data.expires_at
					? Math.floor(new Date(data.expires_at).getTime() / 1000)
					: null,
			});
			return refreshedToken;
		} catch {
			return null;
		}
	})().finally(() => { _refreshPromise = null; });
	return _refreshPromise;
}

/** Refresh the current session through the shared, coalesced refresh flow. */
export function refreshSession(): Promise<string | null> {
	return tryRefresh();
}

/**
 * Fence new refreshes while an explicit logout revokes the freshest token.
 * A refresh already running keeps its normal state transition, so callers can
 * await it and revoke the rotated access token without a mint-after-revoke gap.
 */
export function beginSessionRevocation(): Promise<string | null> {
	const pendingRefresh = _refreshPromise;
	_sessionRevocationInProgress = true;
	return pendingRefresh ?? Promise.resolve(null);
}

export function endSessionRevocation(): void {
	_sessionRevocationInProgress = false;
}

function _buildHeaders(token?: string, projectId?: string, extra?: Record<string, string>): Record<string, string> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(extra ?? {}),
	};
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}
	if (projectId) {
		headers['X-Project-Id'] = projectId;
	}
	return headers;
}

async function request<T>(
	path: string,
	options: RequestInit = {},
	token?: string,
	projectId?: string,
	// Fix 3: caller가 401을 직접 처리하는 경우 전역 로그아웃 리다이렉트를 억제할 수 있음
	reqOpts?: { suppressAuthRedirect?: boolean }
): Promise<T> {
	const method = (options.method ?? 'GET').toString().toUpperCase();
	let requestBody: unknown = options.body;
	if (typeof options.body === 'string') {
		try { requestBody = JSON.parse(options.body); } catch { /* non-JSON body */ }
	}
	const mock = await maybeMockJson<T>(method, path, requestBody, token, projectId);
	if (mock !== symbolNoMatch) {
		if (method === 'GET') memoryCache.set(path, { data: mock, timestamp: Date.now() });
		return mock;
	}

	const headers = _buildHeaders(token, projectId, options.headers as Record<string, string>);

	const res = await fetch(`${getBaseUrl()}${path}`, {
		...options,
		headers,
		signal: options.signal ?? AbortSignal.timeout(30_000),
	});

	// 401: access JWT 만료 → refresh 후 1회 재시도
	if (res.status === 401 && token) {
		const allowDuringRevocation = path === '/api/v1/auth/logout' || path === '/api/v1/auth/logout-all';
		const newToken = await tryRefresh({ allowDuringRevocation });
		if (newToken && newToken !== token) {
			const retryHeaders = _buildHeaders(newToken, projectId, options.headers as Record<string, string>);
			const retry = await fetch(`${getBaseUrl()}${path}`, {
				...options,
				headers: retryHeaders,
				signal: options.signal ?? AbortSignal.timeout(30_000),
			});
			if (retry.ok) {
				if (retry.status === 204) return undefined as T;
				return retry.json();
			}
			if (retry.status === 401 && !reqOpts?.suppressAuthRedirect) void handleUnauthorized();
			let detail = retry.statusText;
			try {
				const body = await retry.json();
				detail = formatErrorDetail(body, retry.statusText);
			} catch { /* ignore */ }
			throw new ApiError(retry.status, detail);
		}
		if (!reqOpts?.suppressAuthRedirect) void handleUnauthorized();
		throw new ApiError(401, '세션이 만료되었습니다');
	}

	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = await res.json();
			detail = formatErrorDetail(body, res.statusText);
		} catch {
			detail = await res.text().catch(() => res.statusText);
		}
		if (res.status === 401 && !reqOpts?.suppressAuthRedirect) {
			void handleUnauthorized();
		}
		if (res.status === 403 && path.includes('/admin')) {
			void handleAdminForbidden();
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
		// Fix 3: suppressAuthRedirect=true 시 401에서 전역 로그아웃을 억제함
		opts?: { refresh?: boolean; signal?: AbortSignal; suppressAuthRedirect?: boolean }
	) => {
		let url: string;
		if (opts?.refresh) {
			// 수동 새로고침: origin 직행 + 재저장 (`?refresh=true`)
			url = `${path}${path.includes('?') ? '&' : '?'}refresh=true`;
		} else if (path.includes('refresh=true')) {
			// URL에 이미 refresh=true 포함 — 무변경 (수동 조립된 3개 경로 보존)
			url = path;
		} else {
			// 기본: 백엔드 캐시 opt-in (`?cache=true`)
			url = `${path}${path.includes('?') ? '&' : '?'}cache=true`;
		}
		const signal = opts?.signal
			? AbortSignal.any([opts.signal, AbortSignal.timeout(30_000)])
			: undefined;
		return request<T>(url, { method: 'GET', signal }, token, projectId, { suppressAuthRedirect: opts?.suppressAuthRedirect });
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
		if (token) headers['Authorization'] = `Bearer ${token}`;
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
				detail = formatErrorDetail(body, res.statusText);
			} catch {
				detail = await res.text().catch(() => res.statusText);
			}
			if (res.status === 401) void handleUnauthorized();
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
			if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
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
					if (xhr.status === 401) void handleUnauthorized();
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
			if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
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
					if (xhr.status === 401) void handleUnauthorized();
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
					const body = xhr.responseText?.slice(0, 400) || '';
					console.error('[S3 PUT] HTTP error', { status: xhr.status, body });
					reject(new ApiError(xhr.status, `PUT failed: ${xhr.status}`));
				}
			};
			xhr.onerror = () => {
				console.error('[S3 PUT] onerror (network failure)', {
					status: xhr.status,
					readyState: xhr.readyState,
					url: url.split('?')[0],
				});
				reject(new ApiError(0, '네트워크 오류가 발생했습니다'));
			};
			xhr.onabort = () => reject(new ApiError(0, '업로드가 취소되었습니다'));
			signal?.addEventListener('abort', () => xhr.abort());
			xhr.send(body);
		});
	},

	downloadBlob: async (path: string, token?: string, projectId?: string): Promise<{ blob: Blob; filename: string }> => {
		const mock = await maybeMockBlob('GET', path, token, projectId);
		if (mock !== symbolNoMatch) return { blob: mock, filename: 'afterglow-mockup-kubeconfig.yaml' };
		const headers: Record<string, string> = { 'Content-Type': 'application/json' };
		if (token) headers['Authorization'] = `Bearer ${token}`;
		if (projectId) headers['X-Project-Id'] = projectId;
		const res = await fetch(`${getBaseUrl()}${path}`, {
			method: 'GET',
			headers,
			signal: AbortSignal.timeout(300_000),
		});
		if (!res.ok) {
			let detail = res.statusText;
			try { detail = (await res.json())?.detail || detail; } catch { /* empty */ }
			if (res.status === 401) void handleUnauthorized();
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
		const mockStream = maybeMockK3sStream(path, body, token, projectId);
		if (mockStream) {
			(async () => {
				try {
					for await (const message of mockStream) onMessage?.(message as T);
				} catch (err) {
					onError?.(err instanceof Error ? err : new Error(String(err)));
				}
			})();
			return;
		}
		const baseUrl = getBaseUrl();
		const url = new URL(`${baseUrl}${path}`);

		// POST 요청을 SSE로 처리하기 위해 fetch 사용 후 EventSource로 전환
		// 하지만 EventSource는 POST를 지원하지 않으므로, fetch로 SSE 스트림을 처리
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			'Accept': 'text/event-stream'
		};
		if (token) headers['Authorization'] = `Bearer ${token}`;
		if (projectId) headers['X-Project-Id'] = projectId;

		// fetch로 POST 요청 후 스트림 처리
		fetch(url, {
			method: 'POST',
			headers,
			body: JSON.stringify(body)
		}).then(async (response) => {
			if (!response.ok) {
				const text = await response.text();
				if (response.status === 401) void handleUnauthorized();
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
