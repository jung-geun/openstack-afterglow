import { getBaseUrl } from './client';
import { parseChatRunEvent, type ChatRunEvent, type ChatRunStatus } from './chatContracts';

export class ChatProtocolError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'ChatProtocolError';
	}
}

export class ChatRunReloadRequiredError extends ChatProtocolError {
	constructor() {
		super('chat run journal is no longer available; reload the conversation');
		this.name = 'ChatRunReloadRequiredError';
	}
}

export interface ChatRunDescriptor {
	run_id: string;
	conversation_id: string | null;
	temp_thread_id: string | null;
	status: ChatRunStatus;
	events_url: string;
	cancel_url: string;
}

export interface CreateChatRunOptions {
	token?: string;
	projectId?: string;
	signal?: AbortSignal;
	idempotencyKey?: string;
}

export interface FollowChatRunOptions {
	token?: string;
	projectId?: string;
	afterSeq?: number;
	signal?: AbortSignal;
}

type SseFrame = { id?: string; event?: string; data: string };
const RUN_STATUSES = [
	'queued',
	'running',
	'awaiting_approval',
	'awaiting_input',
	'waiting_children',
	'finalizing',
	'completed',
	'failed',
	'canceled'
] as const satisfies readonly ChatRunStatus[];

function isRecord(value: unknown): value is Record<string, unknown> {
	return value !== null && typeof value === 'object';
}

function isRunStatus(value: unknown): value is ChatRunStatus {
	return typeof value === 'string' && RUN_STATUSES.some((status) => status === value);
}

function delay(milliseconds: number): Promise<void> {
	const { promise, resolve } = Promise.withResolvers<void>();
	setTimeout(resolve, milliseconds);
	return promise;
}


function headers(token?: string, projectId?: string): HeadersInit {
	const result: Record<string, string> = { Accept: 'text/event-stream' };
	if (token) result.Authorization = `Bearer ${token}`;
	if (projectId) result['X-Project-Id'] = projectId;
	return result;
}

function normalizeDescriptorUrl(url: unknown): string {
	if (typeof url !== 'string' || !url.startsWith('/') || url.startsWith('//')) {
		throw new ChatProtocolError('invalid chat run descriptor');
	}
	if (url.startsWith('/v1/')) {
		return `/api/v1/chat${url.slice(3)}`;
	}
	if (url.startsWith('/api/v1/chat/')) {
		return url;
	}
	throw new ChatProtocolError('invalid chat run descriptor');
}

export function parseChatRunDescriptor(value: unknown): ChatRunDescriptor {
	if (!isRecord(value)) throw new ChatProtocolError('invalid chat run descriptor');
	if (
		typeof value.run_id !== 'string' ||
		(typeof value.conversation_id !== 'string' && value.conversation_id !== null) ||
		(typeof value.temp_thread_id !== 'string' && value.temp_thread_id !== null) ||
		!isRunStatus(value.status)
	) {
		throw new ChatProtocolError('invalid chat run descriptor');
	}
	const eventsUrl = normalizeDescriptorUrl(value.events_url);
	const cancelUrl = normalizeDescriptorUrl(value.cancel_url);
	return {
		run_id: value.run_id,
		conversation_id: value.conversation_id,
		temp_thread_id: value.temp_thread_id,
		status: value.status,
		events_url: eventsUrl,
		cancel_url: cancelUrl
	};
}

async function errorFrom(response: Response): Promise<Error> {
	let detail = `chat request failed (${response.status})`;
	try {
		const body: unknown = await response.json();
		if (isRecord(body) && typeof body.detail === 'string') {
			detail = body.detail;
		}
	} catch {
		// Keep the status-derived message when a proxy returned non-JSON.
	}
	return new ChatProtocolError(detail);
}

/** Creates exactly one durable run. The key remains stable for a caller retry. */
export async function createChatRun(
	path: string,
	body: unknown,
	{ token, projectId, signal, idempotencyKey = crypto.randomUUID() }: CreateChatRunOptions = {}
): Promise<ChatRunDescriptor> {
	const response = await fetch(`${getBaseUrl()}${path}`, {
		method: 'POST',
		headers: {
			...headers(token, projectId),
			'Content-Type': 'application/json',
			'Idempotency-Key': idempotencyKey
		},
		body: JSON.stringify(body),
		signal
	});
	if (response.status !== 202) throw await errorFrom(response);
	return parseChatRunDescriptor(await response.json());
}

function takeFrames(buffer: string): { frames: SseFrame[]; rest: string } {
	const frames: SseFrame[] = [];
	let boundary: number;
	while ((boundary = buffer.search(/\r?\n\r?\n/)) >= 0) {
		const raw = buffer.slice(0, boundary);
		const separatorLength = buffer[boundary] === '\r' ? (buffer[boundary + 1] === '\n' && buffer[boundary + 2] === '\r' ? 4 : 2) : 2;
		buffer = buffer.slice(boundary + separatorLength);
		let id: string | undefined;
		let event: string | undefined;
		const data: string[] = [];
		for (const line of raw.split(/\r?\n/)) {
			if (!line || line.startsWith(':')) continue;
			const colon = line.indexOf(':');
			const field = colon < 0 ? line : line.slice(0, colon);
			const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
			if (field === 'id') id = value;
			else if (field === 'event') event = value;
			else if (field === 'data') data.push(value);
		}
		if (data.length) frames.push({ id, event, data: data.join('\n') });
	}
	return { frames, rest: buffer };
}

async function* decodeFrames(body: ReadableStream<Uint8Array>): AsyncGenerator<SseFrame> {
	const reader = body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';
	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });
			const parsed = takeFrames(buffer);
			buffer = parsed.rest;
			yield* parsed.frames;
		}
		buffer += decoder.decode();
		const parsed = takeFrames(buffer);
		yield* parsed.frames;
		if (parsed.rest.trim()) throw new ChatProtocolError('unterminated SSE frame');
	} finally {
		reader.releaseLock();
	}
}

function eventsUrlWithAfterSeq(eventsUrl: string, afterSeq: number): string {
	const separator = eventsUrl.includes('?') ? '&' : '?';
	return `${eventsUrl}${separator}after_seq=${afterSeq}`;
}

/**
 * Replays the durable journal then tails it. Connection loss is never cancellation:
 * only transport failures retry, and every retry resumes at the last accepted seq.
 */
export async function* followChatRun(
	descriptor: ChatRunDescriptor,
	{ token, projectId, afterSeq = 0, signal }: FollowChatRunOptions = {}
): AsyncGenerator<ChatRunEvent> {
	let lastSeq = afterSeq;
	let attempts = 0;
	const waits = [250, 500, 1000];
	while (true) {
		let response: Response;
		try {
			response = await fetch(`${getBaseUrl()}${eventsUrlWithAfterSeq(descriptor.events_url, lastSeq)}`, {
				headers: { ...headers(token, projectId), ...(lastSeq ? { 'Last-Event-ID': `${descriptor.run_id}:${lastSeq}` } : {}) },
				signal
			});
		} catch (error) {
			if (signal?.aborted) throw error;
			if (attempts >= waits.length) throw new ChatProtocolError('chat event stream disconnected');
			await delay(waits[attempts++]);
			continue;
		}
		if (response.status === 410) throw new ChatRunReloadRequiredError();
		if (!response.ok || !response.body) throw await errorFrom(response);
		try {
			for await (const frame of decodeFrames(response.body)) {
				let raw: unknown;
				try {
					raw = JSON.parse(frame.data);
				} catch {
					throw new ChatProtocolError('chat event is not valid JSON');
				}
				const event = parseChatRunEvent(raw);
				if (frame.id && frame.id !== event.event_id) throw new ChatProtocolError('SSE event id mismatch');
				if (frame.event && frame.event !== event.type) throw new ChatProtocolError('SSE event type mismatch');
				if (event.run_id !== descriptor.run_id) throw new ChatProtocolError('SSE event run mismatch');
				if (event.seq <= lastSeq) continue;
				if (event.seq !== lastSeq + 1) throw new ChatProtocolError('chat event sequence gap');
				lastSeq = event.seq;
				attempts = 0;
				yield event;
				if (event.type === 'run.completed' || event.type === 'run.failed' || event.type === 'run.canceled') return;
			}
		} catch (error) {
			if (signal?.aborted || error instanceof ChatProtocolError) throw error;
		}
		if (attempts >= waits.length) throw new ChatProtocolError('chat event stream disconnected');
		await delay(waits[attempts++]);
	}
}

export async function cancelChatRun(
	descriptor: ChatRunDescriptor,
	{ token, projectId, signal }: Omit<CreateChatRunOptions, 'idempotencyKey'> = {}
): Promise<void> {
	const response = await fetch(`${getBaseUrl()}${descriptor.cancel_url}`, {
		method: 'POST',
		headers: headers(token, projectId),
		signal
	});
	if (!response.ok) throw await errorFrom(response);
}

export const __test__ = { eventsUrlWithAfterSeq, takeFrames };
