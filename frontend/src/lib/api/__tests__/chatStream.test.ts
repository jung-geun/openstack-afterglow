import { describe, expect, it } from 'vitest';
import { __test__, ChatProtocolError, parseChatRunDescriptor } from '../chatStream';

describe('durable chat SSE framing', () => {
	it('preserves multiline data and ignores keepalive comments', () => {
		const parsed = __test__.takeFrames(
			': keepalive\n\nid: run-1:1\nevent: part.delta\ndata: {"first":\ndata: "second"}\n\n'
		);
		expect(parsed.rest).toBe('');
		expect(parsed.frames).toEqual([
			{ id: 'run-1:1', event: 'part.delta', data: '{"first":\n"second"}' }
		]);
	});

	it('retains incomplete frames for the next UTF-8 decode chunk', () => {
		const parsed = __test__.takeFrames('id: run-1:1\ndata: {"type":"run.started"}');
		expect(parsed.frames).toEqual([]);
		expect(parsed.rest).toContain('run.started');
	});

	it('appends replay position after existing descriptor query parameters', () => {
		expect(__test__.eventsUrlWithAfterSeq('/api/v1/chat/runs/run-1/events?ticket=abc', 7)).toBe(
			'/api/v1/chat/runs/run-1/events?ticket=abc&after_seq=7'
		);
	});

	it('identifies malformed protocol failures distinctly', () => {
		expect(new ChatProtocolError('bad event').name).toBe('ChatProtocolError');
	});

	it.each(['awaiting_input', 'waiting_children'] as const)(
		'accepts the v2 %s descriptor status',
		(status) => {
			expect(
				parseChatRunDescriptor({
					run_id: 'run-1',
					conversation_id: 'conversation-1',
					temp_thread_id: null,
					status,
					events_url: '/v1/runs/run-1/events',
					cancel_url: '/v1/runs/run-1/cancel'
				})
			).toMatchObject({
				status,
				events_url: '/api/v1/chat/runs/run-1/events',
				cancel_url: '/api/v1/chat/runs/run-1/cancel'
			});
		}
	);

	it('rejects absolute and cross-origin descriptor URLs', () => {
		expect(() =>
			parseChatRunDescriptor({
				run_id: 'run-1',
				conversation_id: 'conv-1',
				temp_thread_id: null,
				status: 'running',
				events_url: 'http://evil.com/v1/runs/run-1/events',
				cancel_url: '/v1/runs/run-1/cancel'
			})
		).toThrow(ChatProtocolError);

		expect(() =>
			parseChatRunDescriptor({
				run_id: 'run-1',
				conversation_id: 'conv-1',
				temp_thread_id: null,
				status: 'running',
				events_url: '//evil.com/v1/runs/run-1/events',
				cancel_url: '/v1/runs/run-1/cancel'
			})
		).toThrow(ChatProtocolError);
	});
});
