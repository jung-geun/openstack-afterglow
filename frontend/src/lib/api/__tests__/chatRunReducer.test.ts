import { describe, expect, it } from 'vitest';
import { parseChatRunEvent } from '../chatContracts';
import { createRunViewState, reduceRunEvent } from '../chatRunReducer';

const at = '2026-07-21T00:00:00Z';

function event(seq: number, type: string, payload: object) {
	return parseChatRunEvent({
		event_id: `run-1:${seq}`,
		run_id: 'run-1',
		seq,
		type,
		created_at: at,
		payload
	});
}

describe('chat run reducer', () => {
	it('accumulates ordered deltas and replaces them with canonical completed parts', () => {
		let state = createRunViewState('run-1');
		state = reduceRunEvent(state, event(1, 'run.started', { conversation_id: 'c1', temp_thread_id: null, model_name: 'm', effective_features: {} }));
		state = reduceRunEvent(state, event(2, 'message.created', { message_id: '42', role: 'assistant', parent_id: '1' }));
		state = reduceRunEvent(state, event(3, 'part.delta', { message_id: '42', part_index: 0, part_type: 'text', delta: 'hel' }));
		state = reduceRunEvent(state, event(4, 'part.delta', { message_id: '42', part_index: 0, part_type: 'text', delta: 'lo' }));
		state = reduceRunEvent(state, event(5, 'part.completed', { message_id: '42', part_index: 0, part: { type: 'text', text: 'hello' } }));
		expect(state.parts).toEqual([{ type: 'text', text: 'hello' }]);
		expect(state.messageId).toBe('42');
	});

	it('retains the latest persisted stage and its start time after replay', () => {
		let state = createRunViewState('run-1');
		state = reduceRunEvent(
			state,
			event(1, 'run.stage.changed', { stage: 'queued', tool_name: null })
		);
		state = reduceRunEvent(
			state,
			event(2, 'run.stage.changed', { stage: 'tool_execution', tool_name: 'web_search' })
		);
		expect(state).toMatchObject({
			stage: 'tool_execution',
			stageToolName: 'web_search',
			stageStartedAt: at
		});
	});

	it('deduplicates old events and rejects a sequence gap', () => {
		const state = createRunViewState('run-1');
		const started = { conversation_id: null, temp_thread_id: null, model_name: 'm', effective_features: {} };
		const afterStarted = reduceRunEvent(state, event(1, 'run.started', started));
		expect(reduceRunEvent(afterStarted, event(1, 'run.started', started))).toBe(afterStarted);
		expect(() => reduceRunEvent(afterStarted, event(3, 'run.started', started))).toThrow('sequence gap');
	});
});
