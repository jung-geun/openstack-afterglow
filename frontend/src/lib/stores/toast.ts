import { writable } from 'svelte/store';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastAction {
	label: string;
	onClick: () => void;
}

export interface Toast {
	id: string;
	type: ToastType;
	message: string;
	duration: number;
	action?: ToastAction;
}

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);

	function addToast(type: ToastType, message: string, duration = 4000, action?: ToastAction): string {
		const id = crypto.randomUUID();
		update(toasts => [...toasts, { id, type, message, duration, action }]);
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
		success: (msg: string, duration?: number, action?: ToastAction) => addToast('success', msg, duration, action),
		error: (msg: string, duration = 6000, action?: ToastAction) => addToast('error', msg, duration, action),
		warning: (msg: string, duration?: number, action?: ToastAction) => addToast('warning', msg, duration, action),
		info: (msg: string, duration?: number, action?: ToastAction) => addToast('info', msg, duration, action),
		remove: removeToast,
	};
}

export const toast = createToastStore();
