import { getContext, setContext } from 'svelte';
import { api, ApiError } from '$lib/api/client';
import type { AdminVolumeDetail } from '$lib/types/resources';

interface Options {
	volumeId: () => string;
	token: () => string | undefined;
	projectId: () => string | undefined;
	onClose?: () => void;
	onRefresh?: () => void;
}

function createAdminVolumeDetailStore(opts: Options) {
	let volume = $state<AdminVolumeDetail | null>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		const id = opts.volumeId();
		if (!id) return;
		loading = true;
		error = '';
		volume = null;
		fetchVolume();
	});

	async function fetchVolume() {
		try {
			volume = await api.get<AdminVolumeDetail>(`/api/admin/volumes/${opts.volumeId()}`, opts.token(), opts.projectId());
		} catch (e) {
			error = e instanceof ApiError ? e.message : '볼륨 조회 실패';
		} finally {
			loading = false;
		}
	}

	return {
		get volume() { return volume; },
		get loading() { return loading; },
		get error() { return error; },
		fetchVolume,
	};
}

export type AdminVolumeDetailStore = ReturnType<typeof createAdminVolumeDetailStore>;
export { createAdminVolumeDetailStore };

const ADMIN_VOLUME_DETAIL_KEY = Symbol('admin-volume-detail');

export function provideAdminVolumeDetail(store: AdminVolumeDetailStore) {
	setContext(ADMIN_VOLUME_DETAIL_KEY, store);
}

export function useAdminVolumeDetail(): AdminVolumeDetailStore {
	const store = getContext<AdminVolumeDetailStore | undefined>(ADMIN_VOLUME_DETAIL_KEY);
	if (!store) throw new Error('useAdminVolumeDetail must be called within AdminVolumeDetailPanel');
	return store;
}
