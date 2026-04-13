import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from '../client';

// fetch mock
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// SvelteKit env mock
vi.mock('$env/dynamic/public', () => ({
  env: { PUBLIC_API_BASE: 'http://localhost:8000' },
}));

// window/AbortSignal mock
vi.stubGlobal('window', {
  location: { protocol: 'http:', hostname: 'localhost' },
});

describe('API Client — 보안 테스트', () => {
  beforeEach(() => {
    vi.resetModules();
    mockFetch.mockReset();
  });

  it('ApiError는 status와 message를 포함함', () => {
    const err = new ApiError(403, 'Forbidden');
    expect(err.status).toBe(403);
    expect(err.message).toBe('Forbidden');
    expect(err).toBeInstanceOf(Error);
  });

  it('비정상 응답 시 ApiError 발생', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: '인증이 필요합니다' }),
      text: async () => '인증이 필요합니다',
    });

    const { api } = await import('../client');
    await expect(api.get('/api/test', 'bad-token', 'proj-1')).rejects.toThrow(Error);
  });

  it('204 응답 시 undefined 반환', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => ({}),
    });

    const { api } = await import('../client');
    const result = await api.delete('/api/test', 'token', 'proj');
    expect(result).toBeUndefined();
  });

  it('GET 요청에 X-Auth-Token 헤더 포함', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: 'ok' }),
    });

    const { api } = await import('../client');
    await api.get('/api/test', 'my-secret-token', 'my-project');

    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers['X-Auth-Token']).toBe('my-secret-token');
    expect(options.headers['X-Project-Id']).toBe('my-project');
  });

  it('SSE 요청 실패 시 onError 콜백 호출됨', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'));

    const { api } = await import('../client');
    const onError = vi.fn();

    api.postSse('/api/test', {}, 'token', 'proj', undefined, onError);

    // 비동기 처리 대기
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(onError).toHaveBeenCalledWith(expect.any(Error));
  });

  it('SSE 응답 비정상 시 onError 콜백 호출됨', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Server Error',
    });

    const { api } = await import('../client');
    const onError = vi.fn();

    api.postSse('/api/test', {}, 'token', 'proj', undefined, onError);

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(onError).toHaveBeenCalledWith(expect.any(Error));
  });

  it('AbortSignal timeout이 30초로 설정됨', async () => {
    const abortSpy = vi.spyOn(AbortSignal, 'timeout');
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });

    const { api } = await import('../client');
    await api.get('/api/test', 'tok', 'proj');

    expect(abortSpy).toHaveBeenCalledWith(30_000);
  });
});
