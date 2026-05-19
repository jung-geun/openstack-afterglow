import { memoryCache } from '$lib/api/client';

export function createSwr(getProjectId: () => string | null | undefined) {
  function swrGet<T>(path: string): T | null {
    const c = memoryCache.get(`${path}:${getProjectId()}`);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${getProjectId()}`, { data, timestamp: Date.now() });
  }
  return { swrGet, swrSet };
}
