import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

export type ThemePreference = 'dark' | 'light' | 'system';

function createThemeStore() {
	const initial: ThemePreference = browser
		? ((localStorage.getItem('union_theme') as ThemePreference) ?? 'system')
		: 'system';

	const { subscribe, set, update } = writable<ThemePreference>(initial);

	return {
		subscribe,
		set(value: ThemePreference) {
			if (browser) localStorage.setItem('union_theme', value);
			set(value);
		},
		toggle() {
			update(current => {
				const order: ThemePreference[] = ['system', 'dark', 'light'];
				const next = order[(order.indexOf(current) + 1) % order.length];
				if (browser) localStorage.setItem('union_theme', next);
				return next;
			});
		},
	};
}

export const theme = createThemeStore();

/** 시스템 설정 기반 실제 적용 테마 */
function createResolvedTheme() {
	const systemPrefersDark = writable(
		browser ? window.matchMedia('(prefers-color-scheme: dark)').matches : true
	);

	if (browser) {
		const mql = window.matchMedia('(prefers-color-scheme: dark)');
		mql.addEventListener('change', (e) => systemPrefersDark.set(e.matches));
	}

	return derived([theme, systemPrefersDark], ([$theme, $dark]) => {
		if ($theme === 'system') return $dark ? 'dark' : 'light';
		return $theme;
	});
}

export const resolvedTheme = createResolvedTheme();
