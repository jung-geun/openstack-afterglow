import { writable } from 'svelte/store';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
	id: string;
	type: ToastType;
	message: string;
	duration: number;
}

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);

	function addToast(type: ToastType, message: string, duration = 4000): string {
		const id = crypto.randomUUID();
		update(toasts => [...toasts, { id, type, message, duration }]);
		if (duration > 0) {
			setTimeout(() => removeToast(id), duration);
		}
		return id;
	}

	function removeToast(id: string) {
		update(toasts => toasts.filter(t => t.id !== id));
	}

	return {
		subscribe,
		success: (msg: string, duration?: number) => addToast('success', msg, duration),
		error: (msg: string, duration = 6000) => addToast('error', msg, duration),
		warning: (msg: string, duration?: number) => addToast('warning', msg, duration),
		info: (msg: string, duration?: number) => addToast('info', msg, duration),
		remove: removeToast,
	};
}

export const toast = createToastStore();
