export type IntentPrefetchRun = (signal: AbortSignal) => void | Promise<void>;

interface IdleCapableWindow {
	requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
	cancelIdleCallback?: (handle: number) => void;
}

export function createIntentPrefetchScheduler() {
	let currentKey: string | null = null;
	let currentRun: IntentPrefetchRun | null = null;
	let controller: AbortController | null = null;
	let idleHandle: number | null = null;
	let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
	let started = false;

	function cancelTimer(): void {
		const idleWindow = window as unknown as IdleCapableWindow;
		if (idleHandle !== null) idleWindow.cancelIdleCallback?.(idleHandle);
		clearTimeout(timeoutHandle ?? undefined);
		idleHandle = null;
		timeoutHandle = null;
	}

	function start(): void {
		if (started || !currentRun || !controller) return;
		cancelTimer();
		started = true;
		void Promise.resolve(currentRun(controller.signal)).catch(() => undefined);
	}

	function cancel(): void {
		cancelTimer();
		controller?.abort();
		controller = null;
		currentKey = null;
		currentRun = null;
		started = false;
	}

	function prepare(key: string, run: IntentPrefetchRun): void {
		if (currentKey === key) return;
		cancel();
		currentKey = key;
		currentRun = run;
		controller = new AbortController();
	}

	function schedule(key: string | null, run: IntentPrefetchRun): void {
		if (!key) {
			cancel();
			return;
		}
		prepare(key, run);
		if (started || idleHandle !== null || timeoutHandle !== null) return;
		const idleWindow = window as unknown as IdleCapableWindow;
		if (idleWindow.requestIdleCallback) {
			idleHandle = idleWindow.requestIdleCallback(start, { timeout: 1_000 });
		} else {
			timeoutHandle = setTimeout(start, 200);
		}
	}

	function intent(key: string | null, run: IntentPrefetchRun): void {
		if (!key) return;
		prepare(key, run);
		start();
	}

	return { schedule, intent, cancel };
}
