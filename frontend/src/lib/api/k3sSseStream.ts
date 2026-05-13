import { getBaseUrl } from './client';

export interface K3sSseProgressMessage {
  step: string;
  progress: number;
  message: string;
  cluster_id?: string;
  error?: string;
  elapsed_seconds?: number;
}

export async function* streamK3sProgress(
  path: string,
  init: { method: 'POST'; body?: unknown; token?: string; projectId?: string },
): AsyncGenerator<K3sSseProgressMessage> {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    method: init.method,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(init.token ? { 'X-Auth-Token': init.token } : {}),
      ...(init.projectId ? { 'X-Project-Id': init.projectId } : {}),
    },
    body: init.body != null ? JSON.stringify(init.body) : undefined,
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        yield JSON.parse(line.slice(6)) as K3sSseProgressMessage;
      } catch {
        // 파싱 실패한 라인은 무시
      }
    }
  }
}
