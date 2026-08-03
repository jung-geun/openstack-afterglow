export interface ChatRevealBuffer {
	append(delta: string, cadenceAtMs?: number, receivedAtMs?: number): void;
	reconcile(text: string): void;
	frame(nowMs?: number): { text: string; pending: boolean };
	finish(receivedAtMs?: number): void;
	drain(): string;
	clear(): void;
}

interface ScheduledChunk {
	text: string;
	startedAtMs: number;
	endsAtMs: number;
	revealedCharacters: number;
}

/**
 * Smooths authoritative SSE chunks for display only. The journal text is never
 * changed: terminal events can always drain to the exact server-confirmed value.
 *
 * The newest chunk is briefly reserved. If another chunk arrives first, the
 * journal timestamps determine its playback duration while the browser clock
 * determines when that playback starts. A bounded fallback starts playback
 * when a provider pauses, so the reserve never turns a long upstream gap into
 * a second equally long visual gap.
 */
export function createChatRevealBuffer(options: {
	reducedMotion: boolean;
	maxHoldMs?: number;
	maxPlaybackMs?: number;
}): ChatRevealBuffer {
	const maxHoldMs = Math.max(16, options.maxHoldMs ?? 200);
	const maxPlaybackMs = Math.max(maxHoldMs, options.maxPlaybackMs ?? 1000);
	let authoritativeText = '';
	let displayed = '';
	let reservedChunk: { text: string; cadenceAtMs: number; receivedAtMs: number } | null = null;
	let scheduledChunks: ScheduledChunk[] = [];
	let nextScheduledAtMs = 0;
	let fallbackPlaybackMs = maxPlaybackMs;

	function boundedPlaybackMs(durationMs: number) {
		return Math.min(maxPlaybackMs, Math.max(16, durationMs));
	}

	function scheduleChunk(text: string, startedAtMs: number, durationMs: number) {
		const startMs = Math.max(startedAtMs, nextScheduledAtMs);
		const playbackMs = boundedPlaybackMs(durationMs);
		scheduledChunks.push({
			text,
			startedAtMs: startMs,
			endsAtMs: startMs + playbackMs,
			revealedCharacters: 0
		});
		nextScheduledAtMs = startMs + playbackMs;
	}

	function scheduleReservedFromNextArrival(nextCadenceAtMs: number, nextReceivedAtMs: number) {
		if (reservedChunk === null) return;
		const playbackMs = boundedPlaybackMs(nextCadenceAtMs - reservedChunk.cadenceAtMs);
		fallbackPlaybackMs = playbackMs;
		scheduleChunk(reservedChunk.text, nextReceivedAtMs, playbackMs);
	}

	function scheduleReservedFallback(nowMs: number) {
		if (reservedChunk === null || nowMs - reservedChunk.receivedAtMs < maxHoldMs) return;
		scheduleChunk(
			reservedChunk.text,
			reservedChunk.receivedAtMs + maxHoldMs,
			fallbackPlaybackMs
		);
		reservedChunk = null;
	}

	function revealScheduledChunks(nowMs: number) {
		for (const chunk of scheduledChunks) {
			if (nowMs < chunk.startedAtMs) break;

			const durationMs = chunk.endsAtMs - chunk.startedAtMs;
			const progress = Math.min(1, (nowMs - chunk.startedAtMs) / durationMs);
			const revealCount = Math.floor(chunk.text.length * progress);
			if (revealCount > chunk.revealedCharacters) {
				displayed += chunk.text.slice(chunk.revealedCharacters, revealCount);
				chunk.revealedCharacters = revealCount;
			}
			if (progress < 1) break;
		}

		while (
			scheduledChunks[0] !== undefined &&
			scheduledChunks[0].revealedCharacters === scheduledChunks[0].text.length
		) {
			scheduledChunks.shift();
		}
	}

	function unrevealedText() {
		return (
			scheduledChunks
				.map((chunk) => chunk.text.slice(chunk.revealedCharacters))
				.join('') + (reservedChunk?.text ?? '')
		);
	}

	return {
		append(delta, cadenceAtMs = performance.now(), receivedAtMs = cadenceAtMs) {
			authoritativeText += delta;
			if (reservedChunk !== null) {
				scheduleReservedFromNextArrival(cadenceAtMs, receivedAtMs);
			}
			reservedChunk = { text: delta, cadenceAtMs, receivedAtMs };
		},
		reconcile(text) {
			authoritativeText = text;
			if (!text.startsWith(displayed)) {
				displayed = '';
				scheduledChunks = [];
				reservedChunk = null;
				nextScheduledAtMs = 0;
			}

			const remainingText = text.slice(displayed.length);
			if (remainingText !== unrevealedText()) {
				scheduledChunks = [];
				reservedChunk = remainingText
					? {
							text: remainingText,
							cadenceAtMs: performance.now(),
							receivedAtMs: performance.now()
						}
					: null;
				nextScheduledAtMs = 0;
			}
		},
		frame(nowMs = performance.now()) {
			if (options.reducedMotion) {
				displayed = authoritativeText;
				scheduledChunks = [];
				reservedChunk = null;
			} else {
				scheduleReservedFallback(nowMs);
				revealScheduledChunks(nowMs);
			}
			return {
				text: displayed,
				pending: scheduledChunks.length > 0 || reservedChunk !== null
			};
		},
		finish(receivedAtMs = performance.now()) {
			if (reservedChunk === null) return;
			scheduleChunk(reservedChunk.text, receivedAtMs, fallbackPlaybackMs);
			reservedChunk = null;
		},
		drain() {
			displayed = authoritativeText;
			return displayed;
		},
		clear() {
			authoritativeText = '';
			displayed = '';
			reservedChunk = null;
			scheduledChunks = [];
			nextScheduledAtMs = 0;
			fallbackPlaybackMs = maxPlaybackMs;
		}
	};
}
