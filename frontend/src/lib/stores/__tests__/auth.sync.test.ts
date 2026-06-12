import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import type { AuthState } from '../auth';

// jsdom의 실제 window/localStorage를 사용해 탭 간 storage 동기화를 검증한다.
// (auth.test.ts와 달리 window를 stub하지 않음 — storage 이벤트 리스너가 등록되어야 함)

function makeState(overrides: Partial<AuthState>): Partial<AuthState> {
	return {
		token: 'access-1',
		refreshToken: 'refresh-1',
		accessExpiresAt: 1234567890,
		userId: 'user-1',
		username: 'tester',
		projectId: 'proj-1',
		projectName: 'Test Project',
		...overrides,
	};
}

describe('auth 탭 간 동기화 (storage 이벤트)', () => {
	let auth: Writable<AuthState>;
	let setAuth: (typeof import('../auth'))['setAuth'];

	beforeEach(async () => {
		localStorage.clear();
		vi.resetModules();
		const mod = await import('../auth');
		auth = mod.auth as typeof auth;
		setAuth = mod.setAuth;
		mod.clearAuth();
	});

	function dispatchStorage(newValue: string | null) {
		window.dispatchEvent(
			new StorageEvent('storage', { key: 'afterglow_auth', newValue })
		);
	}

	it('다른 탭이 회전시킨 토큰이 이 탭의 store에 반영됨', () => {
		setAuth(makeState({}) as Partial<AuthState> & { token: string });

		const rotated = { ...get(auth), token: 'access-2', refreshToken: 'refresh-2' };
		dispatchStorage(JSON.stringify(rotated));

		const state = get(auth);
		expect(state.token).toBe('access-2');
		expect(state.refreshToken).toBe('refresh-2');
	});

	it('다른 탭에서 로그아웃하면(newValue=null) 이 탭도 초기화됨', () => {
		setAuth(makeState({}) as Partial<AuthState> & { token: string });

		dispatchStorage(null);

		const state = get(auth);
		expect(state.token).toBeNull();
		expect(state.refreshToken).toBeNull();
	});

	it('관련 없는 key의 storage 이벤트는 무시됨', () => {
		setAuth(makeState({}) as Partial<AuthState> & { token: string });

		window.dispatchEvent(
			new StorageEvent('storage', { key: 'other_key', newValue: '{"token":"hacked"}' })
		);

		expect(get(auth).token).toBe('access-1');
	});

	it('손상된 JSON은 무시되고 기존 상태 유지', () => {
		setAuth(makeState({}) as Partial<AuthState> & { token: string });

		dispatchStorage('{invalid-json');

		expect(get(auth).token).toBe('access-1');
	});

	it('token 없는 페이로드는 무시됨 (로그아웃은 null로만 전파)', () => {
		setAuth(makeState({}) as Partial<AuthState> & { token: string });

		dispatchStorage(JSON.stringify({ username: 'evil' }));

		const state = get(auth);
		expect(state.token).toBe('access-1');
		expect(state.username).toBe('tester');
	});

	it('store 갱신 시 localStorage에 영속화됨 (동기화의 전제)', () => {
		setAuth(makeState({}) as Partial<AuthState> & { token: string });

		const raw = localStorage.getItem('afterglow_auth');
		expect(raw).not.toBeNull();
		expect(JSON.parse(raw!).token).toBe('access-1');
	});
});
