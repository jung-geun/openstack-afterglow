import { describe, expect, it } from 'vitest';
import { createChatRevealBuffer } from '../chatRevealBuffer';

describe('createChatRevealBuffer', () => {
	it('reserves a chunk until the next arrival, then plays it across their actual interval', () => {
		const buffer = createChatRevealBuffer({ reducedMotion: false });
		buffer.append('warm', 0);
		expect(buffer.frame(0)).toEqual({ text: '', pending: true });

		buffer.append('abcdefgh', 100);
		expect(buffer.frame(100)).toEqual({ text: '', pending: true });
		expect(buffer.frame(150)).toEqual({ text: 'wa', pending: true });
		expect(buffer.frame(200)).toEqual({ text: 'warm', pending: true });
	});

	it('keeps burst chunks queued and continuously reveals them after the next arrival', () => {
		const buffer = createChatRevealBuffer({ reducedMotion: false });
		buffer.append('aaaa', 0);
		buffer.append('bbbb', 100);
		buffer.append('cccc', 200);

		expect(buffer.frame(200)).toEqual({ text: 'aaaa', pending: true });
		expect(buffer.frame(250)).toEqual({ text: 'aaaabb', pending: true });
		expect(buffer.frame(300)).toEqual({ text: 'aaaabbbb', pending: true });
	});

	it('uses journal cadence when a poll delivers multiple chunks at once', () => {
		const buffer = createChatRevealBuffer({ reducedMotion: false });
		buffer.append('aaaa', 1_000, 100);
		buffer.append('bbbb', 1_100, 101);
		buffer.append('cccc', 1_200, 102);

		expect(buffer.frame(102)).toEqual({ text: '', pending: true });
		expect(buffer.frame(151)).toEqual({ text: 'aa', pending: true });
		expect(buffer.frame(201)).toEqual({ text: 'aaaa', pending: true });
		expect(buffer.frame(251)).toEqual({ text: 'aaaabb', pending: true });
		expect(buffer.frame(301)).toEqual({ text: 'aaaabbbb', pending: true });
	});

	it('falls back to bounded playback instead of doubling a long provider pause', () => {
		const buffer = createChatRevealBuffer({
			reducedMotion: false,
			maxHoldMs: 200,
			maxPlaybackMs: 500
		});
		buffer.append('slow', 0);

		expect(buffer.frame(199)).toEqual({ text: '', pending: true });
		expect(buffer.frame(200)).toEqual({ text: '', pending: true });
		expect(buffer.frame(450)).toEqual({ text: 'sl', pending: true });
		expect(buffer.frame(700)).toEqual({ text: 'slow', pending: false });
	});

	it('schedules the final reserved chunk instead of draining it immediately', () => {
		const buffer = createChatRevealBuffer({
			reducedMotion: false,
			maxHoldMs: 100,
			maxPlaybackMs: 200
		});
		buffer.append('final', 0);
		buffer.finish(100);

		expect(buffer.frame(100)).toEqual({ text: '', pending: true });
		expect(buffer.frame(200)).toEqual({ text: 'fi', pending: true });
		expect(buffer.frame(300)).toEqual({ text: 'final', pending: false });
	});

	it('keeps corrected authoritative text when completion follows reconciliation', () => {
		const buffer = createChatRevealBuffer({
			reducedMotion: false,
			maxHoldMs: 100,
			maxPlaybackMs: 200
		});
		buffer.append('wrong', 0);
		buffer.reconcile('right');
		buffer.finish(100);

		expect(buffer.frame(100)).toEqual({ text: '', pending: true });
		expect(buffer.frame(300)).toEqual({ text: 'right', pending: false });
	});

	it('reconciles an authoritative completed part before draining', () => {
		const buffer = createChatRevealBuffer({ reducedMotion: false });
		buffer.append('partial', 0);
		buffer.frame(0);
		buffer.reconcile('partial response');
		expect(buffer.drain()).toBe('partial response');
	});

	it('clears a prior assistant turn before revealing the next one', () => {
		const buffer = createChatRevealBuffer({ reducedMotion: true });
		buffer.append('previous turn', 0);
		expect(buffer.frame(0).text).toBe('previous turn');

		buffer.clear();
		buffer.append('next turn', 1);
		expect(buffer.frame(1).text).toBe('next turn');
	});

	it('drains immediately when reduced motion is requested', () => {
		const buffer = createChatRevealBuffer({ reducedMotion: true });
		buffer.append('accessible', 0);
		expect(buffer.frame(0)).toEqual({ text: 'accessible', pending: false });
	});
});
