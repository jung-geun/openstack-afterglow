import { getContext, setContext } from 'svelte';
import { api, ApiError } from '$lib/api/client';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';
import type { FileStorage, AccessRule } from '$lib/types/fileStorage';

export const statusColor: Record<string, string> = {
	available: 'text-green-400 bg-green-900/30',
	creating: 'text-yellow-400 bg-yellow-900/30',
	deleting: 'text-orange-400 bg-orange-900/30',
	error: 'text-red-400 bg-red-900/30',
};

interface Options {
	fileStorageId: () => string;
	token: () => string | undefined;
	projectId: () => string | undefined;
	onDeleted?: () => void;
	onClose?: () => void;
}

function createFileStorageDetailController(opts: Options) {
	let fileStorage = $state<FileStorage | null>(null);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);
	let copiedIndex = $state<number | null>(null);

	let accessRules = $state<AccessRule[]>([]);
	let accessLoading = $state(false);
	let accessError = $state('');
	let showAddRule = $state(false);
	let ruleForm = $state({ access_to: '', access_level: 'ro' });
	let addingRule = $state(false);
	let ruleError = $state('');
	let revokingId = $state<string | null>(null);
	let copiedKey = $state<string | null>(null);

	async function fetchFileStorage() {
		loading = true;
		error = '';
		try {
			fileStorage = await api.get<FileStorage>(
				`/api/file-storage/${opts.fileStorageId()}`,
				opts.token(),
				opts.projectId()
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function fetchAccessRules() {
		accessLoading = true;
		accessError = '';
		try {
			accessRules = await api.get<AccessRule[]>(
				`/api/file-storage/${opts.fileStorageId()}/access-rules`,
				opts.token(),
				opts.projectId()
			);
		} catch (e) {
			accessRules = [];
			accessError = e instanceof ApiError ? `접근 규칙 로드 실패 (${e.status}): ${e.message}` : '접근 규칙을 불러오지 못했습니다';
		} finally {
			accessLoading = false;
		}
	}

	async function fetchAll() {
		await Promise.all([fetchFileStorage(), fetchAccessRules()]);
	}

	async function addAccessRule() {
		if (!fileStorage || !ruleForm.access_to.trim()) return;
		addingRule = true;
		ruleError = '';
		const access_type = fileStorage.share_proto === 'NFS' ? 'ip' : 'cephx';
		try {
			await api.post(
				`/api/file-storage/${fileStorage.id}/access-rules`,
				{ access_to: ruleForm.access_to.trim(), access_level: ruleForm.access_level, access_type },
				opts.token(),
				opts.projectId()
			);
			ruleForm = { access_to: '', access_level: 'ro' };
			showAddRule = false;
			await fetchAccessRules();
		} catch (e) {
			ruleError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			addingRule = false;
		}
	}

	async function revokeAccessRule(accessId: string) {
		if (!fileStorage) return;
		if (!(await confirmDialog('이 접근 규칙을 삭제하시겠습니까?'))) return;
		revokingId = accessId;
		try {
			await api.delete(
				`/api/file-storage/${fileStorage.id}/access-rules/${accessId}`,
				opts.token(),
				opts.projectId()
			);
			await fetchAccessRules();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			revokingId = null;
		}
	}

	async function copyPath(path: string, index: number) {
		await navigator.clipboard.writeText(path);
		copiedIndex = index;
		setTimeout(() => (copiedIndex = null), 2000);
	}

	async function copyKey(key: string, id: string) {
		await navigator.clipboard.writeText(key);
		copiedKey = id;
		setTimeout(() => (copiedKey = null), 2000);
	}

	async function deleteFileStorage() {
		if (!fileStorage) return;
		if (!(await confirmDialog(`파일 스토리지 "${fileStorage.name || fileStorage.id}"를 삭제하시겠습니까?`))) return;
		deleting = true;
		try {
			await api.delete(`/api/file-storage/${fileStorage.id}`, opts.token(), opts.projectId());
			opts.onDeleted?.();
			opts.onClose?.();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}

	return {
		get fileStorage() { return fileStorage; },
		get loading() { return loading; },
		get error() { return error; },
		get deleting() { return deleting; },
		get copiedIndex() { return copiedIndex; },
		get accessRules() { return accessRules; },
		get accessLoading() { return accessLoading; },
		get accessError() { return accessError; },
		get showAddRule() { return showAddRule; },
		set showAddRule(v: boolean) { showAddRule = v; },
		get ruleForm() { return ruleForm; },
		get addingRule() { return addingRule; },
		get ruleError() { return ruleError; },
		get revokingId() { return revokingId; },
		get copiedKey() { return copiedKey; },
		fetchAll,
		addAccessRule,
		revokeAccessRule,
		copyPath,
		copyKey,
		deleteFileStorage,
	};
}

export type FileStorageDetailController = ReturnType<typeof createFileStorageDetailController>;
export { createFileStorageDetailController };

const FS_DETAIL_KEY = Symbol('fs-detail');

export function provideFileStorageDetailController(store: FileStorageDetailController) {
	setContext(FS_DETAIL_KEY, store);
}

export function useFileStorageDetailController(): FileStorageDetailController {
	const store = getContext<FileStorageDetailController | undefined>(FS_DETAIL_KEY);
	if (!store) throw new Error('useFileStorageDetailController must be called within FileStorageDetailPanel');
	return store;
}
