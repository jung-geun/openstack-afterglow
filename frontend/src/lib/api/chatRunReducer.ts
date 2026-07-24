import type { ChatPart, ChatRunEvent, RunStage, UsageComponent } from './chatContracts';

export interface RunToolView {
	callId: string;
	name: string;
	arguments: Record<string, unknown>;
	status: 'running' | 'completed' | 'failed';
	content: ChatPart[];
}

export interface RunViewState {
	runId: string;
	lastSeq: number;
	status: 'queued' | 'running' | 'awaiting_approval' | 'finalizing' | 'completed' | 'failed' | 'canceled';
	messageId: string | null;
	parts: ChatPart[];
	tools: Record<string, RunToolView>;
	usage: { promptTokens: number; completionTokens: number; components: UsageComponent[] } | null;
	error: string | null;
	stage: RunStage | null;
	stageStartedAt: string | null;
	stageToolName: string | null;
}

export function createRunViewState(runId: string): RunViewState {
	return {
		runId,
		lastSeq: 0,
		status: 'queued',
		messageId: null,
		parts: [],
		tools: {},
		usage: null,
		error: null,
		stage: null,
		stageStartedAt: null,
		stageToolName: null,
	};
}

function replacePart(parts: ChatPart[], index: number, part: ChatPart): ChatPart[] {
	const next = parts.slice();
	next[index] = part;
	return next;
}

function applyDelta(parts: ChatPart[], index: number, type: 'text' | 'reasoning', delta: string): ChatPart[] {
	const existing = parts[index];
	if (existing?.type === type) {
		return replacePart(parts, index, { ...existing, text: existing.text + delta });
	}
	const part: ChatPart = type === 'text' ? { type: 'text', text: delta } : { type: 'reasoning', text: delta, visibility: 'user' };
	return replacePart(parts, index, part);
}

/** Applies a strictly contiguous event; duplicates are harmless and gaps are rejected. */
export function reduceRunEvent(state: RunViewState, event: ChatRunEvent): RunViewState {
	if (event.run_id !== state.runId) throw new Error('chat event run mismatch');
	if (event.seq <= state.lastSeq) return state;
	if (event.seq !== state.lastSeq + 1) throw new Error('chat event sequence gap');
	let next: RunViewState = { ...state, lastSeq: event.seq };

	switch (event.type) {
		case 'run.started':
			next.status = 'running';
			break;
		case 'run.stage.changed':
			next.stage = event.payload.stage;
			next.stageStartedAt = event.created_at;
			next.stageToolName = event.payload.tool_name;
			break;
		case 'message.created':
			next.messageId = event.payload.message_id;
			break;
		case 'part.delta':
			next.parts = applyDelta(next.parts, event.payload.part_index, event.payload.part_type, event.payload.delta);
			break;
		case 'part.completed':
			next.parts = replacePart(next.parts, event.payload.part_index, event.payload.part);
			break;
		case 'tool.call.started':
			next.tools = {
				...next.tools,
				[event.payload.call_id]: {
					callId: event.payload.call_id,
					name: event.payload.name,
					arguments: event.payload.arguments,
					status: 'running',
					content: []
				}
			};
			break;
		case 'tool.call.completed': {
			const existing = next.tools[event.payload.call_id];
			next.tools = {
				...next.tools,
				[event.payload.call_id]: {
					callId: event.payload.call_id,
					name: event.payload.name,
					arguments: existing?.arguments ?? {},
					status: event.payload.status,
					content: event.payload.content
				}
			};
			break;
		}
		case 'usage.updated':
			next.usage = {
				promptTokens: event.payload.prompt_tokens,
				completionTokens: event.payload.completion_tokens,
				components: event.payload.components
			};
			break;
		case 'run.completed':
			next.status = 'completed';
			next.messageId = event.payload.message_id;
			break;
		case 'run.failed':
		case 'run.canceled':
			next.status = event.payload.status;
			next.messageId = event.payload.message_id;
			next.error = event.payload.safe_message;
			break;
		default:
			break;
	}
	return next;
}
