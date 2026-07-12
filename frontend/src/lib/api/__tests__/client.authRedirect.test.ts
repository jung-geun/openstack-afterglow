import { beforeEach, describe, expect, it, vi } from 'vitest';

const { goto, clearAuth, mockFetch, auth, logoutInProgress, setAuth, session, logoutState } = vi.hoisted(() => {
	const session = {
		value: { token: 'session-token', refreshToken: 'refresh-token' as string | null, accessExpiresAt: null as number | null },
	};
	const logoutState = { value: false };
	return {
		goto: vi.fn(),
		clearAuth: vi.fn(),
		mockFetch: vi.fn(),
		auth: {
			subscribe: (run: (value: typeof session.value) => void) => {
				run(session.value);
				return () => {};
			},
		},
		logoutInProgress: {
			subscribe: (run: (value: boolean) => void) => {
				run(logoutState.value);
				return () => {};
			},
		},
		setAuth: vi.fn((next: Partial<typeof session.value>) => {
			session.value = { ...session.value, ...next };
		}),
		session,
		logoutState,
	};
});

vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/stores/auth', () => ({
	auth,
	clearAuth,
	getMockupProfile: () => null,
	isMockAuthActive: () => false,
	logoutInProgress,
	setAuth,
}));
vi.mock('$env/dynamic/public', () => ({
	env: { PUBLIC_API_BASE: 'http://localhost:8000' },
}));

vi.stubGlobal('fetch', mockFetch);

describe('unauthorized API redirect', () => {
	let replace = vi.fn();

	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
		session.value = { token: 'session-token', refreshToken: 'refresh-token', accessExpiresAt: null };
		logoutState.value = false;
		localStorage.clear();
		replace = vi.fn();
		goto.mockResolvedValue(undefined);
		vi.stubGlobal('window', {
			location: {
				pathname: '/dashboard',
				protocol: 'http:',
				hostname: 'localhost',
				replace,
			},
		});
		mockFetch.mockResolvedValue({
			ok: false,
			status: 401,
			statusText: 'Unauthorized',
			json: async () => ({ detail: '인증이 필요합니다' }),
			text: async () => '인증이 필요합니다',
		});
	});

	it('replaces history when an unauthorized request clears the session', async () => {
		const { api, ApiError } = await import('../client');

		await expect(api.get('/api/v1/protected', 'expired-token', 'project')).rejects.toBeInstanceOf(ApiError);
		await vi.waitFor(() => expect(clearAuth).toHaveBeenCalledOnce());

		expect(goto).toHaveBeenCalledWith('/login', { replaceState: true });
		expect(replace).not.toHaveBeenCalled();
	});

	it('uses location.replace when Svelte navigation rejects', async () => {
		goto.mockRejectedValueOnce(new Error('navigation failure'));
		const { api, ApiError } = await import('../client');

		await expect(api.get('/api/v1/protected', 'expired-token', 'project')).rejects.toBeInstanceOf(ApiError);
		await vi.waitFor(() => expect(replace).toHaveBeenCalledWith('/login'));
	});

	it('coalesces concurrent unauthorized redirects before dynamic imports resolve', async () => {
		session.value = { ...session.value, refreshToken: null };
		const { api } = await import('../client');

		await Promise.allSettled([
			api.get('/api/v1/protected-a', 'expired-token', 'project'),
			api.get('/api/v1/protected-b', 'expired-token', 'project'),
		]);

		await vi.waitFor(() => expect(clearAuth).toHaveBeenCalledOnce());
		expect(goto).toHaveBeenCalledOnce();
		expect(goto).toHaveBeenCalledWith('/login', { replaceState: true });
	});
	it('coalesces concurrent explicit refreshes through the public helper', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: true,
			json: async () => ({
				token: 'rotated-token',
				refresh_token: 'rotated-refresh-token',
				expires_at: '2026-07-11T00:00:00Z',
			}),
		});
		const { refreshSession } = await import('../client');

		const [first, second] = await Promise.all([refreshSession(), refreshSession()]);

		expect(mockFetch).toHaveBeenCalledOnce();
		expect(mockFetch).toHaveBeenCalledWith(
			'http://localhost:8000/api/v1/auth/refresh',
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ refresh_token: 'refresh-token' }),
			}),
		);
		expect(first).toBe('rotated-token');
		expect(second).toBe('rotated-token');
		expect(setAuth).toHaveBeenCalledWith(expect.objectContaining({
			token: 'rotated-token',
			refreshToken: 'rotated-refresh-token',
		}));
	});

	it('fences new refreshes while preserving a captured response for logout revocation', async () => {
		let resolveRefresh!: (response: {
			ok: boolean;
			json: () => Promise<{ token: string; refresh_token: string; expires_at: string }>;
		}) => void;
		mockFetch.mockImplementationOnce(() => new Promise((resolve) => {
			resolveRefresh = resolve;
		}));
		const { refreshSession, beginSessionRevocation, endSessionRevocation } = await import('../client');

		const pendingRefresh = refreshSession();
		await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledOnce());
		const pendingRevocation = beginSessionRevocation();
		try {
			await expect(refreshSession()).resolves.toBeNull();
			resolveRefresh({
				ok: true,
				json: async () => ({
					token: 'rotated-token',
					refresh_token: 'rotated-refresh-token',
					expires_at: '2026-07-11T00:00:00Z',
				}),
			});

			await expect(pendingRefresh).resolves.toBe('rotated-token');
			await expect(pendingRevocation).resolves.toBe('rotated-token');
			expect(setAuth).toHaveBeenCalledWith(expect.objectContaining({
				token: 'rotated-token',
				refreshToken: 'rotated-refresh-token',
			}));
		} finally {
			endSessionRevocation();
		}
	});

	it('leaves logout-owned cleanup alone when an unrelated request receives 401', async () => {
		const { api, ApiError, beginSessionRevocation, endSessionRevocation } = await import('../client');
		logoutState.value = true;
		beginSessionRevocation();
		try {
			await expect(api.get('/api/v1/protected', 'expired-token', 'project')).rejects.toBeInstanceOf(ApiError);
			expect(clearAuth).not.toHaveBeenCalled();
			expect(goto).not.toHaveBeenCalled();
		} finally {
			endSessionRevocation();
		}
	});

	it('refreshes an expired token only to complete a fenced logout request', async () => {
		mockFetch
			.mockResolvedValueOnce({
				ok: false,
				status: 401,
				statusText: 'Unauthorized',
				json: async () => ({ detail: 'expired' }),
			})
			.mockResolvedValueOnce({
				ok: true,
				json: async () => ({
					token: 'logout-refresh-token',
					refresh_token: 'logout-refresh-refresh-token',
					expires_at: '2026-07-11T00:00:00Z',
				}),
			})
			.mockResolvedValueOnce({
				ok: true,
				status: 200,
				json: async () => ({ message: '로그아웃 완료' }),
			});
		const { api, beginSessionRevocation, endSessionRevocation } = await import('../client');
		logoutState.value = true;
		beginSessionRevocation();
		try {
			await expect(api.post('/api/v1/auth/logout', {}, 'expired-token', 'project')).resolves.toEqual({
				message: '로그아웃 완료',
			});

			expect(mockFetch).toHaveBeenCalledTimes(3);
			expect(mockFetch.mock.calls[1][0]).toBe('http://localhost:8000/api/v1/auth/refresh');
			expect(mockFetch.mock.calls[2][0]).toBe('http://localhost:8000/api/v1/auth/logout');
			expect(mockFetch.mock.calls[2][1].headers.Authorization).toBe('Bearer logout-refresh-token');
		} finally {
			endSessionRevocation();
		}
	});

	it('adopts a cross-tab refresh winner before revoking the session', async () => {
		let resolveRefresh!: (response: {
			ok: boolean;
			json: () => Promise<{ token: string; refresh_token: string; expires_at: string }>;
		}) => void;
		mockFetch.mockImplementationOnce(() => new Promise((resolve) => {
			resolveRefresh = resolve;
		}));
		const { refreshSession, beginSessionRevocation, endSessionRevocation } = await import('../client');

		const pendingRefresh = refreshSession();
		await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledOnce());
		const pendingRevocation = beginSessionRevocation();
		localStorage.setItem('afterglow_auth', JSON.stringify({
			token: 'winner-token',
			refreshToken: 'winner-refresh-token',
			accessExpiresAt: 1_783_920_000,
		}));
		try {
			resolveRefresh({
				ok: false,
				json: async () => ({
					token: '',
					refresh_token: '',
					expires_at: '',
				}),
			});

			await expect(pendingRefresh).resolves.toBe('winner-token');
			await expect(pendingRevocation).resolves.toBe('winner-token');
			expect(setAuth).toHaveBeenCalledWith({
				token: 'winner-token',
				refreshToken: 'winner-refresh-token',
				accessExpiresAt: 1_783_920_000,
			});
		} finally {
			endSessionRevocation();
			localStorage.clear();
		}
	});
});
