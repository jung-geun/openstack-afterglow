import { describe, expect, it } from 'vitest';
import {
	ChatContractError,
	defaultChatFeatureOptions,
	parseChatPartsForDisplay,
	parseChatPartsStrict,
	parseChatRunEvent
} from '../chatContracts';

describe('chatContracts', () => {
	it('keeps the canonical safe defaults', () => {
		expect(defaultChatFeatureOptions()).toMatchObject({
			memory: true,
			output_modalities: ['text'],
			web_search: { enabled: false },
			web_fetch: { enabled: false },
			advisor: { enabled: false },
			tool_policy: { mode: 'agent_default', approval_mode: 'required_for_mutations' }
		});
	});

	it('rejects unknown input parts but safely degrades display parts', () => {
		expect(() => parseChatPartsStrict([{ type: 'future_provider_block', secret: 'never render' }])).toThrow(ChatContractError);
		expect(parseChatPartsForDisplay([{ type: 'future_provider_block', secret: 'never render' }])).toEqual([
			{ type: 'unknown', original_type: 'future_provider_block' }
		]);
	});

	it('validates a canonical part-completed event and rejects cursor mismatch', () => {
		const event = {
			event_id: 'run-1:1',
			run_id: 'run-1',
			seq: 1,
			type: 'part.completed',
			created_at: '2026-07-21T00:00:00Z',
			payload: { message_id: '1', part_index: 0, part: { type: 'text', text: 'hello' } }
		};
		expect(parseChatRunEvent(event)).toMatchObject({ type: 'part.completed', seq: 1 });
		expect(() => parseChatRunEvent({ ...event, event_id: 'run-1:2' })).toThrow(ChatContractError);
	});

	it('parses a persisted stage event with a tool name only during execution', () => {
		expect(
			parseChatRunEvent({
				event_id: 'run-1:2',
				run_id: 'run-1',
				seq: 2,
				type: 'run.stage.changed',
				created_at: '2026-07-21T00:00:00Z',
				payload: { stage: 'tool_execution', tool_name: 'web_search' }
			})
		).toMatchObject({ type: 'run.stage.changed', payload: { tool_name: 'web_search' } });
		expect(() =>
			parseChatRunEvent({
				event_id: 'run-1:2',
				run_id: 'run-1',
				seq: 2,
				type: 'run.stage.changed',
				created_at: '2026-07-21T00:00:00Z',
				payload: { stage: 'queued', tool_name: 'web_search' }
			})
		).toThrow(ChatContractError);
	});
	it.each([
		['run.completed', { status: 'completed', message_id: '1' }],
		['run.failed', { status: 'failed', message_id: null, error_code: 'provider_error', safe_message: 'Provider failed.' }],
		['run.canceled', { status: 'canceled', message_id: '1', error_code: 'canceled_by_user', safe_message: 'Canceled.' }]
	] as const)('parses the typed %s terminal payload', (type, payload) => {
		expect(
			parseChatRunEvent({
				event_id: 'run-1:2',
				run_id: 'run-1',
				seq: 2,
				type,
				created_at: '2026-07-21T00:00:00Z',
				payload
			})
		).toMatchObject({ type, payload });
	});
});
