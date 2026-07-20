/**
 * 채팅 SSE 스트림 파서.
 *
 * `api.postSse` 는 콜백 기반이고 중단(abort)을 지원하지 않는다. 채팅은 사용자가
 * 응답을 도중에 멈출 수 있어야 하므로, fetch + ReadableStream 을 AbortController 로
 * 감싼 async generator 를 별도로 제공한다.
 *
 * 서버는 각 라인 `data: {json}\n\n` 형식으로 이벤트를 흘린다. json.type:
 * - token       : {text} 텍스트 델타(누적)
 * - reasoning   : {text} 추론(thinking) 델타 — 최종 답변과 분리, 저장 안 함
 * - tool_call   : {name} 도구 호출 진행(스피너)
 * - tool_calls  : {content, calls:[{id,name,args}]} 도구 호출(인자) — 시각화 카드
 * - tool_result : {tool_call_id, name, content} 도구 실행 결과 — 시각화 카드
 * - citations   : {items:[{url,title,snippet}]} 답변 출처 — 하단 표시 + 패널
 * - error       : {message} 모델 오류(done 안 옴)
 * - done        : {prompt_tokens, completion_tokens, credited_cost} 완료
 */
import { getBaseUrl } from './client';

export interface ChatStreamToken {
	type: 'token';
	text: string;
}
/** 추론(thinking) 델타 — 최종 답변과 분리해 접이식으로 노출. 저장하지 않음. */
export interface ChatStreamReasoning {
	type: 'reasoning';
	text: string;
}
export interface ChatStreamToolCall {
	type: 'tool_call';
	name: string;
}
/** 도구 호출(인자 포함) — 시각화 카드용. */
export interface ChatStreamToolCalls {
	type: 'tool_calls';
	content?: string | null;
	calls: { id?: string | null; name: string; args?: string | null }[];
}
/** 도구 실행 결과 — 시각화 카드용. */
export interface ChatStreamToolResult {
	type: 'tool_result';
	tool_call_id?: string | null;
	name: string;
	content: string;
}
/** 답변 출처 — 하단 리스트 + "출처" 패널. */
export interface ChatStreamCitations {
	type: 'citations';
	items: { url: string; title?: string | null; snippet?: string | null }[];
}
export interface ChatStreamError {
	type: 'error';
	message: string;
}
export interface ChatStreamDone {
	type: 'done';
	prompt_tokens?: number;
	completion_tokens?: number;
	credited_cost?: number;
}
export type ChatStreamEvent =
	| ChatStreamToken
	| ChatStreamReasoning
	| ChatStreamToolCall
	| ChatStreamToolCalls
	| ChatStreamToolResult
	| ChatStreamCitations
	| ChatStreamError
	| ChatStreamDone;

export interface ChatStreamOptions {
	token?: string;
	projectId?: string;
	signal?: AbortSignal;
}

/**
 * POST 로 SSE 스트림을 열고 이벤트를 async generator 로 yield 한다.
 * signal 로 중단하면 fetch 가 취소되고 AbortError 가 던져지므로 호출측에서 처리한다.
 */
export async function* streamChat(
	path: string,
	body: unknown,
	{ token, projectId, signal }: ChatStreamOptions = {}
): AsyncGenerator<ChatStreamEvent, void, unknown> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		Accept: 'text/event-stream'
	};
	if (token) headers['Authorization'] = `Bearer ${token}`;
	// client.ts 와 동일한 케이싱(X-Project-Id) 을 사용한다.
	if (projectId) headers['X-Project-Id'] = projectId;

	const response = await fetch(`${getBaseUrl()}${path}`, {
		method: 'POST',
		headers,
		body: JSON.stringify(body),
		signal
	});

	if (!response.ok) {
		let detail = response.statusText;
		try {
			const text = await response.text();
			if (text) detail = text;
		} catch {
			/* ignore */
		}
		throw new Error(detail || `요청이 실패했습니다 (${response.status})`);
	}

	const reader = response.body?.getReader();
	if (!reader) throw new Error('응답 본문이 없습니다');

	const decoder = new TextDecoder();
	let buffer = '';

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });
			const lines = buffer.split('\n');
			buffer = lines.pop() ?? '';
			for (const line of lines) {
				const trimmed = line.trimEnd();
				if (!trimmed.startsWith('data:')) continue;
				const payload = trimmed.slice(5).trimStart();
				if (!payload) continue;
				let evt: ChatStreamEvent | null = null;
				try {
					evt = JSON.parse(payload) as ChatStreamEvent;
				} catch {
					continue; // 파싱 실패 라인은 무시
				}
				if (evt && typeof evt.type === 'string') yield evt;
			}
		}
	} finally {
		try {
			await reader.cancel();
		} catch {
			/* ignore */
		}
	}
}
