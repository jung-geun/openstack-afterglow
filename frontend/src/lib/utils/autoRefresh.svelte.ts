import { untrack } from 'svelte';

interface AutoRefreshOptions {
	storageKey: string;
	defaultActive?: boolean;
	defaultInterval?: number;
	intervalOptions?: number[];
	invokeOnMount?: boolean;
}

export interface AutoRefreshController {
	active: boolean;
	intervalSeconds: number;
	readonly intervalOptions: number[];
	setBoost(seconds: number | null): void;
}

export function createAutoRefresh(
	fn: () => void | Promise<void>,
	options: AutoRefreshOptions,
): AutoRefreshController {
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

	// 비영속 boost: setBoost(seconds) 로 임시 가속, setBoost(null) 로 해제
	let _boost = $state<number | null>(null);
	function setBoost(seconds: number | null) { _boost = seconds; }

	// 이전 라운드가 끝나기 전 다음 라운드가 겹쳐 실행되지 않도록 in-flight 가드
	let _running = false;
	async function tick() {
		if (_running) return;
		_running = true;
		try { await fn(); } finally { _running = false; }
	}

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
		// _boost를 여기서 읽어야 reactive dependency로 등록됨 (boost 변화 시 timer 재시작)
		const effectiveMs = (_boost ?? state.intervalSeconds) * 1000;

		let timerId: ReturnType<typeof setInterval> | null = null;

		function start() {
			timerId = setInterval(() => {
				tick();
			}, effectiveMs);
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
				tick();
				start();
			}
		}

		if (!document.hidden) {
			if (invokeOnMount) untrack(() => tick());
			start();
		}

		document.addEventListener('visibilitychange', onVisibility);

		return () => {
			stop();
			document.removeEventListener('visibilitychange', onVisibility);
		};
	});

	return {
		get active() { return state.active; },
		set active(v: boolean) { state.active = v; },
		get intervalSeconds() { return state.intervalSeconds; },
		set intervalSeconds(v: number) { state.intervalSeconds = v; },
		get intervalOptions() { return state.intervalOptions; },
		setBoost,
	};
}
