import { getContext, setContext } from 'svelte';
import { api, ApiError } from '$lib/api/client';
import type { ImageDetail, ImageMember } from '$lib/types/adminImage';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';

const RESERVED_KEYS = new Set([
	'id', 'name', 'status', 'visibility', 'owner', 'size', 'virtual_size',
	'disk_format', 'container_format', 'checksum', 'os_hash_algo', 'os_hash_value',
	'min_disk', 'min_ram', 'tags', 'self', 'file', 'schema', 'direct_url',
	'locations', 'created_at', 'updated_at', 'protected', 'os_hidden',
]);

export const isReservedKey = (k: string) => RESERVED_KEYS.has(k) || k.startsWith('os_glance_');

export const VISIBILITY_OPTIONS = [
	{ value: 'public',    label: '공개 (Public)' },
	{ value: 'private',   label: '비공개 (Private)' },
	{ value: 'shared',    label: '공유 (Shared)' },
	{ value: 'community', label: '커뮤니티 (Community)' },
];

export interface ImageDetailControllerOpts {
	imageId: () => string;
	token: () => string | undefined;
	projectId: () => string | undefined;
	isAdmin: () => boolean;
	onDelete?: (id: string) => void;
	onClose?: () => void;
}

export function createImageDetailController(opts: ImageDetailControllerOpts) {
	// Domain state
	let image = $state<ImageDetail | null>(null);
	let members = $state<ImageMember[]>([]);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);

	// Visibility state
	let visibilityValue = $state('');
	let savingVisibility = $state(false);
	let visibilityError = $state('');
	let visibilitySuccess = $state(false);

	// Members state
	let loadingMembers = $state(false);
	let newMemberId = $state('');
	let addingMember = $state(false);
	let memberError = $state('');
	let removingMember = $state<string | null>(null);

	// Properties edit state
	let editingProps = $state(false);
	let propsDraft = $state<Record<string, string>>({});
	let propsRemovedKeys = $state<Set<string>>(new Set());
	let newPropKey = $state('');
	let newPropValue = $state('');
	let savingProps = $state(false);
	let propsError = $state('');

	// Derived
	const isOwner = $derived(image?.owner === opts.projectId());
	const canEditMetadata = $derived(isOwner || opts.isAdmin());
	const propertiesEndpoint = $derived(opts.isAdmin() ? '/api/v1/admin/images' : '/api/v1/images');

	// Handlers
	async function loadImage() {
		const id = opts.imageId();
		const tok = opts.token();
		const proj = opts.projectId();
		if (!id || !tok) return;
		loading = true;
		error = '';
		image = null;
		try {
			image = await api.get<ImageDetail>(`/api/v1/images/${id}`, tok, proj);
			visibilityValue = image.visibility ?? '';
			if (image.visibility === 'shared') loadMembers();
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function loadMembers() {
		const id = opts.imageId();
		const tok = opts.token();
		const proj = opts.projectId();
		loadingMembers = true;
		memberError = '';
		try {
			members = await api.get<ImageMember[]>(`/api/v1/images/${id}/members`, tok, proj);
		} catch {
			members = [];
		} finally {
			loadingMembers = false;
		}
	}

	function reset() {
		image = null;
		members = [];
		loading = true;
		error = '';
		editingProps = false;
		propsDraft = {};
		propsRemovedKeys = new Set();
	}

	async function saveVisibility() {
		if (!image || visibilityValue === image.visibility) return;
		const tok = opts.token();
		const proj = opts.projectId();
		savingVisibility = true;
		visibilityError = '';
		visibilitySuccess = false;
		try {
			const updated = await api.patch<ImageDetail>(
				`/api/v1/images/${image.id}`,
				{ visibility: visibilityValue },
				tok, proj
			);
			image = { ...image, visibility: updated.visibility };
			visibilitySuccess = true;
			setTimeout(() => { visibilitySuccess = false; }, 2000);
			if (updated.visibility === 'shared') loadMembers();
		} catch (e) {
			visibilityError = e instanceof ApiError ? e.message : '저장 실패';
		} finally {
			savingVisibility = false;
		}
	}

	async function addMember() {
		if (!image || !newMemberId.trim()) return;
		const tok = opts.token();
		const proj = opts.projectId();
		addingMember = true;
		memberError = '';
		try {
			await api.post(`/api/v1/images/${image.id}/members`, { member: newMemberId.trim() }, tok, proj);
			newMemberId = '';
			await loadMembers();
		} catch (e) {
			memberError = e instanceof ApiError ? e.message : '멤버 추가 실패';
		} finally {
			addingMember = false;
		}
	}

	async function removeMember(memberId: string) {
		if (!image) return;
		const tok = opts.token();
		const proj = opts.projectId();
		removingMember = memberId;
		memberError = '';
		try {
			await api.delete(`/api/v1/images/${image.id}/members/${memberId}`, tok, proj);
			await loadMembers();
		} catch (e) {
			memberError = e instanceof ApiError ? e.message : '멤버 삭제 실패';
		} finally {
			removingMember = null;
		}
	}

	function startEditProps() {
		if (!image) return;
		propsDraft = { ...image.properties };
		propsRemovedKeys = new Set();
		newPropKey = '';
		newPropValue = '';
		propsError = '';
		editingProps = true;
	}

	function cancelEditProps() {
		editingProps = false;
		propsDraft = {};
		propsRemovedKeys = new Set();
		propsError = '';
	}

	function removeProperty(key: string) {
		if (isReservedKey(key)) return;
		delete propsDraft[key];
		propsDraft = { ...propsDraft };
		propsRemovedKeys.add(key);
		propsRemovedKeys = new Set(propsRemovedKeys);
	}

	function addProperty() {
		const key = newPropKey.trim();
		const value = newPropValue.trim();
		if (!key) {
			propsError = '키를 입력하세요.';
			return;
		}
		if (isReservedKey(key)) {
			propsError = `"${key}" 는 시스템 예약 키라 편집할 수 없습니다.`;
			return;
		}
		propsDraft[key] = value;
		propsDraft = { ...propsDraft };
		propsRemovedKeys.delete(key);
		propsRemovedKeys = new Set(propsRemovedKeys);
		newPropKey = '';
		newPropValue = '';
		propsError = '';
	}

	async function saveProperties() {
		if (!image) return;
		const tok = opts.token();
		const proj = opts.projectId();
		const pendingKey = newPropKey.trim();
		if (pendingKey && !isReservedKey(pendingKey)) {
			propsDraft[pendingKey] = newPropValue.trim();
			propsDraft = { ...propsDraft };
			propsRemovedKeys.delete(pendingKey);
			propsRemovedKeys = new Set(propsRemovedKeys);
			newPropKey = '';
			newPropValue = '';
		}
		const original = image.properties;
		const setObj: Record<string, string> = {};
		for (const [k, v] of Object.entries(propsDraft)) {
			if (isReservedKey(k)) continue;
			if (original[k] !== v) setObj[k] = v;
		}
		const removeList = Array.from(propsRemovedKeys).filter((k) => !isReservedKey(k));
		if (Object.keys(setObj).length === 0 && removeList.length === 0) {
			editingProps = false;
			return;
		}
		savingProps = true;
		propsError = '';
		try {
			const updated = await api.patch<ImageDetail>(
				`${propertiesEndpoint}/${image.id}/properties`,
				{ set: setObj, remove: removeList },
				tok, proj
			);
			image = { ...image, properties: updated.properties };
			editingProps = false;
		} catch (e) {
			propsError = e instanceof ApiError ? e.message : '저장 실패';
		} finally {
			savingProps = false;
		}
	}

	async function deleteImage() {
		if (!image) return;
		const tok = opts.token();
		const proj = opts.projectId();
		if (!(await confirmDialog(`이미지 "${image.name}"을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`))) return;
		deleting = true;
		try {
			await api.delete(`/api/v1/images/${image.id}`, tok, proj);
			opts.onDelete?.(image.id);
			opts.onClose?.();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			deleting = false;
		}
	}

	return {
		// State getters
		get image() { return image; },
		get members() { return members; },
		get loading() { return loading; },
		get error() { return error; },
		get deleting() { return deleting; },
		get visibilityValue() { return visibilityValue; },
		set visibilityValue(v: string) { visibilityValue = v; },
		get savingVisibility() { return savingVisibility; },
		get visibilityError() { return visibilityError; },
		get visibilitySuccess() { return visibilitySuccess; },
		get loadingMembers() { return loadingMembers; },
		get newMemberId() { return newMemberId; },
		set newMemberId(v: string) { newMemberId = v; },
		get addingMember() { return addingMember; },
		get memberError() { return memberError; },
		get removingMember() { return removingMember; },
		get editingProps() { return editingProps; },
		get propsDraft() { return propsDraft; },
		get propsRemovedKeys() { return propsRemovedKeys; },
		get newPropKey() { return newPropKey; },
		set newPropKey(v: string) { newPropKey = v; },
		get newPropValue() { return newPropValue; },
		set newPropValue(v: string) { newPropValue = v; },
		get savingProps() { return savingProps; },
		get propsError() { return propsError; },
		// Derived getters
		get isOwner() { return isOwner; },
		get canEditMetadata() { return canEditMetadata; },
		get isAdmin() { return opts.isAdmin(); },
		// Handlers
		loadImage,
		loadMembers,
		reset,
		saveVisibility,
		addMember,
		removeMember,
		startEditProps,
		cancelEditProps,
		removeProperty,
		addProperty,
		saveProperties,
		deleteImage,
	};
}

export type ImageDetailController = ReturnType<typeof createImageDetailController>;

const IMAGE_DETAIL_KEY = Symbol('image-detail');

export function provideImageDetailController(store: ImageDetailController) {
	setContext(IMAGE_DETAIL_KEY, store);
}

export function useImageDetailController(): ImageDetailController {
	const store = getContext<ImageDetailController | undefined>(IMAGE_DETAIL_KEY);
	if (!store) throw new Error('useImageDetailController must be called within ImageDetailPanel');
	return store;
}
