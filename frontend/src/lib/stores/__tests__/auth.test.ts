import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import type { AuthState } from '../auth';

// localStorage mock
const storage: Record<string, string> = {};
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, val: string) => { storage[key] = val; },
  removeItem: (key: string) => { delete storage[key]; },
});
vi.stubGlobal('window', { localStorage: globalThis.localStorage });

describe('auth store', () => {
  let auth: Writable<AuthState>;
  let setAuth: typeof import('../auth')['setAuth'];
  let clearAuth: typeof import('../auth')['clearAuth'];
  let isAdmin: typeof import('../auth')['isAdmin'];

  beforeEach(async () => {
    vi.resetModules();
    const mod = await import('../auth');
    auth = mod.auth as typeof auth;
    setAuth = mod.setAuth;
    clearAuth = mod.clearAuth;
    isAdmin = mod.isAdmin;
    clearAuth();
  });

  it('초기 상태는 로그인되지 않음', () => {
    const state = get(auth);
    expect(state.token).toBeNull();
    expect(state.roles).toEqual([]);
  });

  it('setAuth 후 token과 roles가 저장됨', () => {
    setAuth({
      token: 'my-token',
      userId: 'user-1',
      username: 'testuser',
      projectId: 'proj-1',
      projectName: 'Test Project',
      expiresAt: null,
      roles: ['member', 'admin'],
    });
    const state = get(auth);
    expect(state.token).toBe('my-token');
    expect(state.roles).toContain('admin');
  });

  it('isAdmin은 roles에 admin이 있을 때 true', () => {
    setAuth({ token: 'tok', userId: 'u', username: 'u', projectId: 'p', projectName: 'p', expiresAt: null, roles: ['admin'] });
    expect(get(isAdmin)).toBe(true);
  });

  it('isAdmin은 roles에 admin이 없을 때 false', () => {
    setAuth({ token: 'tok', userId: 'u', username: 'u', projectId: 'p', projectName: 'p', expiresAt: null, roles: ['member'] });
    expect(get(isAdmin)).toBe(false);
  });

  it('clearAuth 후 초기 상태로 복원', () => {
    setAuth({ token: 'tok', userId: 'u', username: 'u', projectId: 'p', projectName: 'p', expiresAt: null, roles: ['admin'] });
    clearAuth();
    const state = get(auth);
    expect(state.token).toBeNull();
    expect(state.roles).toEqual([]);
  });
});
