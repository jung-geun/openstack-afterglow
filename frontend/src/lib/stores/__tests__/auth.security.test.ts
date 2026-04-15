import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import type { AuthState } from '../auth';

// localStorage + cookie mock
const storage: Record<string, string> = {};
let cookieString = '';

vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, val: string) => { storage[key] = val; },
  removeItem: (key: string) => { delete storage[key]; },
});

vi.stubGlobal('window', { localStorage: globalThis.localStorage });

// document.cookie mock
Object.defineProperty(globalThis, 'document', {
  value: {
    get cookie() { return cookieString; },
    set cookie(val: string) { cookieString = val; },
  },
  configurable: true,
});

describe('auth store — 보안 테스트', () => {
  let auth: Writable<AuthState>;
  let setAuth: typeof import('../auth')['setAuth'];
  let clearAuth: typeof import('../auth')['clearAuth'];

  beforeEach(async () => {
    vi.resetModules();
    // localStorage 초기화
    Object.keys(storage).forEach((k) => delete storage[k]);
    cookieString = '';

    const mod = await import('../auth');
    auth = mod.auth as typeof auth;
    setAuth = mod.setAuth;
    clearAuth = mod.clearAuth;
    clearAuth();
  });

  it('토큰 설정 시 localStorage에 저장됨', () => {
    setAuth({
      token: 'secret-token-123',
      userId: 'u1',
      username: 'testuser',
      projectId: 'p1',
      projectName: 'MyProject',
      expiresAt: null,
      roles: ['member'],
    });
    expect(storage['afterglow_auth']).toBeTruthy();
    const saved = JSON.parse(storage['afterglow_auth']);
    // 토큰이 localStorage에 저장됨 (현재 동작 — 보안 개선 전)
    expect(saved.token).toBe('secret-token-123');
  });

  it('clearAuth 시 localStorage에서 토큰 제거됨', () => {
    setAuth({
      token: 'secret-token-123',
      userId: 'u1',
      username: 'testuser',
      projectId: 'p1',
      projectName: 'MyProject',
      expiresAt: null,
      roles: ['member'],
    });
    // 저장 확인
    expect(storage['afterglow_auth']).toBeTruthy();

    // 로그아웃
    clearAuth();

    // localStorage에서 제거 확인
    expect(storage['afterglow_auth']).toBeUndefined();
  });

  it('clearAuth 후 auth store의 token이 null', () => {
    setAuth({ token: 'tok', userId: 'u', username: 'u', projectId: 'p', projectName: 'p', expiresAt: null, roles: [] });
    clearAuth();
    expect(get(auth).token).toBeNull();
  });

  it('초기 상태에서 token이 null이면 localStorage에 저장 안 됨', () => {
    clearAuth();
    expect(storage['afterglow_auth']).toBeUndefined();
  });

  it('JSON 파싱 실패 시 초기 상태로 폴백', async () => {
    storage['afterglow_auth'] = 'invalid json {{{';
    vi.resetModules();
    const mod = await import('../auth');
    const state = get(mod.auth);
    expect(state.token).toBeNull();
  });
});
