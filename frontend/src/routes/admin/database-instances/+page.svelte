<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface DbInstance {
		id: string;
		name: string;
		status: string;
		datastore: { type?: string; version?: string };
		flavor_id: string;
		size: number;
		created_at: string;
	}

	interface DbFlavor {
		id: string;
		name: string;
		ram: number;
	}

	interface Datastore {
		id: string;
		name: string;
		versions: { id: string; name: string }[];
	}

	const statusColor: Record<string, string> = {
		ACTIVE: 'text-green-400',
		BUILD: 'text-yellow-400',
		ERROR: 'text-red-400',
		SHUTDOWN: 'text-gray-400',
	};

	let instances = $state<DbInstance[]>([]);
	let loading = $state(true);
	let deleting = $state<string | null>(null);
	let restarting = $state<string | null>(null);

	let showModal = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let flavors = $state<DbFlavor[]>([]);
	let datastores = $state<Datastore[]>([]);
	let form = $state({ name: '', flavor_id: '', volume_size: 5, datastore_type: '', datastore_version: '' });

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);
	const selectedDs = $derived(datastores.find((d) => d.name === form.datastore_type));

	async function load() {
		loading = true;
		try {
			instances = await api.get<DbInstance[]>('/api/database-instances', token, projectId);
		} catch {
			instances = [];
		} finally {
			loading = false;
		}
	}

	async function openModal() {
		showModal = true;
		createError = '';
		form = { name: '', flavor_id: '', volume_size: 5, datastore_type: '', datastore_version: '' };
		try {
			[flavors, datastores] = await Promise.all([
				api.get<DbFlavor[]>('/api/database-instances/flavors', token, projectId),
				api.get<Datastore[]>('/api/database-instances/datastores', token, projectId),
			]);
			if (flavors.length) form.flavor_id = flavors[0].id;
			if (datastores.length) {
				form.datastore_type = datastores[0].name;
				if (datastores[0].versions.length) form.datastore_version = datastores[0].versions[0].name;
			}
		} catch { /* ignore */ }
	}

	async function createInstance() {
		if (!form.name.trim() || !form.flavor_id || !form.datastore_type || !form.datastore_version) return;
		creating = true; createError = '';
		try {
			await api.post('/api/database-instances', { ...form, name: form.name.trim() }, token, projectId);
			showModal = false;
			await load();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : 'DB 인스턴스 생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteInstance(id: string, name: string) {
		if (!confirm(`DB 인스턴스 "${name || id.slice(0, 8)}"를 삭제하시겠습니까?`)) return;
		deleting = id;
		try {
			await api.delete(`/api/database-instances/${id}`, token, projectId);
			await load();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function restartInstance(id: string, name: string) {
		if (!confirm(`DB 인스턴스 "${name || id.slice(0, 8)}"를 재시작하시겠습니까?`)) return;
		restarting = id;
		try {
			await api.post(`/api/database-instances/${id}/restart`, {}, token, projectId);
			await load();
		} catch (e) {
			alert('재시작 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			restarting = null;
		}
	}

	onMount(load);
</script>

{#if showModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { showModal = false; }}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-4">DB 인스턴스 생성</h2>
			<div class="space-y-3">
				<div>
					<label class="block text-xs text-gray-400 mb-1">이름</label>
					<input type="text" bind:value={form.name} placeholder="my-database"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500" />
				</div>
				{#if datastores.length}
					<div>
						<label class="block text-xs text-gray-400 mb-1">데이터스토어</label>
						<select bind:value={form.datastore_type}
							onchange={() => { const ds = datastores.find(d => d.name === form.datastore_type); form.datastore_version = ds?.versions[0]?.name ?? ''; }}
							class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500">
							{#each datastores as ds}<option value={ds.name}>{ds.name}</option>{/each}
						</select>
					</div>
					{#if selectedDs && selectedDs.versions.length}
						<div>
							<label class="block text-xs text-gray-400 mb-1">버전</label>
							<select bind:value={form.datastore_version}
								class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500">
								{#each selectedDs.versions as v}<option value={v.name}>{v.name}</option>{/each}
							</select>
						</div>
					{/if}
				{:else}
					<div class="grid grid-cols-2 gap-2">
						<div>
							<label class="block text-xs text-gray-400 mb-1">데이터스토어 타입</label>
							<input type="text" bind:value={form.datastore_type} placeholder="mysql"
								class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500" />
						</div>
						<div>
							<label class="block text-xs text-gray-400 mb-1">버전</label>
							<input type="text" bind:value={form.datastore_version} placeholder="5.7"
								class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500" />
						</div>
					</div>
				{/if}
				{#if flavors.length}
					<div>
						<label class="block text-xs text-gray-400 mb-1">플레이버</label>
						<select bind:value={form.flavor_id}
							class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500">
							{#each flavors as f}<option value={f.id}>{f.name} ({f.ram} MB RAM)</option>{/each}
						</select>
					</div>
				{:else}
					<div>
						<label class="block text-xs text-gray-400 mb-1">플레이버 ID</label>
						<input type="text" bind:value={form.flavor_id} placeholder="flavor UUID"
							class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500" />
					</div>
				{/if}
				<div>
					<label class="block text-xs text-gray-400 mb-1">볼륨 크기 (GB)</label>
					<input type="number" bind:value={form.volume_size} min="1" max="1024"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500" />
				</div>
				{#if createError}<p class="text-red-400 text-xs">{createError}</p>{/if}
			</div>
			<div class="flex justify-end gap-2 mt-5">
				<button onclick={() => { showModal = false; }}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors">취소</button>
				<button onclick={createInstance} disabled={creating || !form.name.trim()}
					class="px-4 py-2 text-sm bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg transition-colors">
					{creating ? '생성 중...' : '생성'}
				</button>
			</div>
		</div>
	</div>
{/if}

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">DB 인스턴스</h1>
		<div class="flex gap-2">
			<button onclick={openModal}
				class="text-xs text-white bg-amber-600 hover:bg-amber-500 transition-colors px-3 py-1.5 rounded border border-amber-500">+ 인스턴스 생성</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if instances.length === 0}
		<div class="text-gray-600 text-sm">DB 인스턴스가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 px-4 font-medium">이름</th>
						<th class="text-left py-3 px-4 font-medium">상태</th>
						<th class="text-left py-3 px-4 font-medium">Datastore</th>
						<th class="text-left py-3 px-4 font-medium">크기 (GB)</th>
						<th class="text-left py-3 px-4 font-medium">ID</th>
						<th class="text-left py-3 px-4 font-medium">생성일</th>
						<th class="text-right py-3 px-4 font-medium">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each instances as inst}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-3 px-4">
								<a href="/admin/database-instances/{inst.id}" class="text-amber-400 hover:text-amber-300 font-medium">{inst.name}</a>
							</td>
							<td class="py-3 px-4 font-medium text-xs {statusColor[inst.status] ?? 'text-gray-300'}">{inst.status}</td>
							<td class="py-3 px-4 text-gray-300">{inst.datastore?.type ?? '-'} {inst.datastore?.version ?? ''}</td>
							<td class="py-3 px-4 text-gray-300">{inst.size || '-'}</td>
							<td class="py-3 px-4 text-gray-600 font-mono text-xs">{inst.id.slice(0, 8)}…</td>
							<td class="py-3 px-4 text-gray-500 text-xs">{inst.created_at ? inst.created_at.slice(0, 10) : '-'}</td>
							<td class="py-3 px-4 text-right">
								<div class="flex justify-end gap-1">
									<button onclick={() => restartInstance(inst.id, inst.name)} disabled={restarting === inst.id}
										class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors">
										{restarting === inst.id ? '...' : '재시작'}
									</button>
									<button onclick={(e) => { e.stopPropagation(); deleteInstance(inst.id, inst.name); }} disabled={deleting === inst.id}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
										{deleting === inst.id ? '...' : '삭제'}
									</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
