import { ApiError } from './client';
import { toast } from '$lib/stores/toast';

export interface ApiMutOpts {
	successMessage?: string | null;
	errorPrefix?: string;
	progress?: boolean;
	rethrow?: boolean;
}

export async function apiMut<T>(
	label: string,
	fn: () => Promise<T>,
	opts: ApiMutOpts = {}
): Promise<T> {
	const { successMessage, errorPrefix, progress = false, rethrow = true } = opts;
	let progressId: string | undefined;
	if (progress) progressId = toast.info(`${label} 진행 중...`, 0);
	try {
		const result = await fn();
		if (progressId) toast.remove(progressId);
		if (successMessage !== null) toast.success(successMessage ?? `${label} 완료`);
		return result;
	} catch (e) {
		if (progressId) toast.remove(progressId);
		const msg = e instanceof ApiError ? e.message : String(e);
		toast.error(`${errorPrefix ?? label + ' 실패'}: ${msg}`);
		if (rethrow) throw e;
		return undefined as T;
	}
}
