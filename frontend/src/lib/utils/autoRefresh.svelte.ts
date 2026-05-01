import { untrack } from 'svelte';

interface AutoRefreshOptions {
	storageKey: string;
	defaultActive?: boolean;
	defaultInterval?: number;
	intervalOptions?: number[];
	invokeOnMount?: boolean;
}

export function createAutoRefresh(fn: () => void | Promise<void>, options: AutoRefreshOptions) {
	const {
		storageKey,
		defaultActive = true,
		defaultInterval = 30,
		intervalOptions = [10, 15, 30, 60],
		invokeOnMount = true
	} = options;

	const state = $state({
		active: defaultActive,
		intervalSeconds: defaultInterval,
		intervalOptions
	});

	// Restore saved preferences from localStorage (client-only via $effect)
	$effect(() => {
		const savedActive = localStorage.getItem(`autoRefresh.${storageKey}.active`);
		const savedInterval = localStorage.getItem(`autoRefresh.${storageKey}.interval`);
		if (savedActive !== null) state.active = savedActive === 'true';
		if (savedInterval !== null) {
			const n = parseInt(savedInterval, 10);
			if (!isNaN(n) && intervalOptions.includes(n)) state.intervalSeconds = n;
		}
	});

	// Persist preferences whenever they change
	$effect(() => {
		localStorage.setItem(`autoRefresh.${storageKey}.active`, String(state.active));
		localStorage.setItem(`autoRefresh.${storageKey}.interval`, String(state.intervalSeconds));
	});

	// Timer management + Page Visibility API
	$effect(() => {
		if (!state.active) return;

		let timerId: ReturnType<typeof setInterval> | null = null;

		function start() {
			timerId = setInterval(() => {
				fn();
			}, state.intervalSeconds * 1000);
		}

		function stop() {
			if (timerId !== null) {
				clearInterval(timerId);
				timerId = null;
			}
		}

		function onVisibility() {
			if (document.hidden) {
				stop();
			} else {
				stop();
				fn();
				start();
			}
		}

		if (!document.hidden) {
			if (invokeOnMount) untrack(() => fn());
			start();
		}

		document.addEventListener('visibilitychange', onVisibility);

		return () => {
			stop();
			document.removeEventListener('visibilitychange', onVisibility);
		};
	});

	return state;
}
