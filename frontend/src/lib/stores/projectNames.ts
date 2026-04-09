import { writable } from 'svelte/store';
import { api } from '$lib/api/client';

const nameMap = writable<Map<string, string>>(new Map());
let loaded = false;

async function load(token?: string, projectId?: string) {
	if (loaded) return;
	try {
		const data: { id: string; name: string }[] = await api.get('/api/admin/projects/names', token, projectId);
		const map = new Map<string, string>();
		for (const p of data) {
			map.set(p.id, p.name);
		}
		nameMap.set(map);
		loaded = true;
	} catch {
		// 로드 실패 시 빈 맵 유지
	}
}

function reset() {
	loaded = false;
	nameMap.set(new Map());
}

export const projectNames = {
	subscribe: nameMap.subscribe,
	load,
	reset,
};
