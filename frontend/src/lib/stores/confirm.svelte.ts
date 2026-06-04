let _resolve: ((v: boolean) => void) | null = null;
let _open = $state(false);
let _message = $state('');

export function confirmDialog(message: string): Promise<boolean> {
	return new Promise(resolve => {
		_message = message;
		_open = true;
		_resolve = resolve;
	});
}

export const dialogState = {
	get open() { return _open; },
	get message() { return _message; },
	accept() { _open = false; _resolve?.(true); _resolve = null; },
	reject() { _open = false; _resolve?.(false); _resolve = null; },
};
