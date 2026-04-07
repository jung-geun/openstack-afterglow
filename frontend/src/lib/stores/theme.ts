import { writable } from 'svelte/store';
import { browser } from '$app/environment';

type Theme = 'dark' | 'light';

function createThemeStore() {
  const initial: Theme = browser
    ? ((localStorage.getItem('union_theme') as Theme) ?? 'dark')
    : 'dark';

  const { subscribe, set, update } = writable<Theme>(initial);

  return {
    subscribe,
    set(value: Theme) {
      if (browser) localStorage.setItem('union_theme', value);
      set(value);
    },
    toggle() {
      update(current => {
        const next: Theme = current === 'dark' ? 'light' : 'dark';
        if (browser) localStorage.setItem('union_theme', next);
        return next;
      });
    },
  };
}

export const theme = createThemeStore();
