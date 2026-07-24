import { describe, expect, it } from 'vitest';
import { __test__, ChatProtocolError } from '../chatStream';

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

	it('identifies malformed protocol failures distinctly', () => {
		expect(new ChatProtocolError('bad event').name).toBe('ChatProtocolError');
	});
});
