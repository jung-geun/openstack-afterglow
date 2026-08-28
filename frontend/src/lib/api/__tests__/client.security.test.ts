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

  it('SSE 응답 비정상 시 onError 콜백 호출됨', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Server Error',
    });

    const { api } = await import('../client');
    const onError = vi.fn();

    api.postSse('/api/v1/test', {}, 'token', 'proj', undefined, onError);

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
    await api.get('/api/v1/test', 'tok', 'proj');

    expect(abortSpy).toHaveBeenCalledWith(30_000);
  });
});
