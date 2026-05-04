import { writable } from 'svelte/store';

function createPaletteStore() {
  const { subscribe, set } = writable(false);
  return {
    subscribe,
    open: () => set(true),
    close: () => set(false),
    toggle: () => set,
  };
}

export const palette = createPaletteStore();
