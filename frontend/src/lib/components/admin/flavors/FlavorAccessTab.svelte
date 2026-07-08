<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { toast } from '$lib/stores/toast';

	interface Flavor {
		id: string;
		name: string;
		vcpus: number;
		ram: number;
		disk: number;
		is_public: boolean;
		description: string | null;
		extra_specs: Record<string, string>;
		is_gpu: boolean;
		gpu_count: number;
	}
	interface FlavorAccess {
		flavor_id: string;
		project_id: string;
		project_name: string;
	}

	let { flavor }: { flavor: Flavor } = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let accessList = $state<FlavorAccess[]>([]);
	let accessLoading = $state(false);
	let accessError = $state('');
	let addingId = $state<string | null>(null);
	let projectSearch = $state('');
	let allProjects = $state<{ id: string; name: string }[]>([]);

	const accessedProjectIds = $derived(new Set(accessList.map((a) => a.project_id)));
	const availableProjects = $derived(allProjects.filter((p) => !accessedProjectIds.has(p.id)));
	const searchedProjects = $derived(
		projectSearch.trim().length > 0
			? availableProjects
					.filter(
						(p) =>
							p.name.toLowerCase().includes(projectSearch.toLowerCase()) ||
							p.id.toLowerCase().includes(projectSearch.toLowerCase()),
					)
					.slice(0, 8)
			: [],
	);

	$effect(() => {
		if (flavor.id) {
			accessList = [];
			accessError = '';
			projectSearch = '';
			loadAccess();
			if (allProjects.length === 0) {
				api
					.get<{ id: string; name: string }[]>('/api/v1/admin/projects/names', token, projectId)
					.then((r) => (allProjects = r))
					.catch(() => (allProjects = []));
			}
		}
	});

	async function loadAccess() {
		accessLoading = true;
		try {
			accessList = await api.get<FlavorAccess[]>(
				`/api/v1/admin/flavors/${flavor.id}/access`,
				token,
				projectId,
			);
		} catch {
			accessList = [];
		} finally {
			accessLoading = false;
		}
	}

	async function addAccess(pid: string) {
		if (!pid || addingId === pid) return;
		accessError = '';
		addingId = pid;
		try {
			await api.post(
				`/api/v1/admin/flavors/${flavor.id}/access`,
				{ project_id: pid },
				token,
				projectId,
			);
			projectSearch = '';
			toast.success('접근 권한이 추가되었습니다');
			await loadAccess();
		} catch (e) {
			const msg = e instanceof ApiError ? e.message : '접근 권한 추가 실패';
			accessError = msg;
			toast.error(msg);
		} finally {
			addingId = null;
		}
	}

	async function removeAccess(pid: string) {
		try {
			await api.delete(
				`/api/v1/admin/flavors/${flavor.id}/access/${pid}`,
				token,
				projectId,
			);
			await loadAccess();
		} catch {
			accessError = '접근 권한 제거 실패';
		}
	}
</script>

{#if flavor.is_public}
	<div class="bg-gray-800/50 border border-gray-700 text-gray-400 rounded-lg px-4 py-6 text-sm text-center">
		Public Flavor는 모든 프로젝트에서 사용 가능하므로 접근 권한 설정이 필요하지 않습니다.
	</div>
{:else}
	{#if accessError}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{accessError}</div>
	{/if}

	<div class="mb-4">
		<div class="text-sm text-gray-400 mb-2">프로젝트 접근 추가</div>
		<div class="relative">
			<input
				type="text"
				placeholder="프로젝트 이름 또는 ID 검색..."
				bind:value={projectSearch}
				class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
			/>
			{#if searchedProjects.length > 0}
				<div class="absolute z-10 left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden">
					{#each searchedProjects as p}
						<div class="flex items-center justify-between px-3 py-2 hover:bg-gray-700 border-b border-gray-700/50 last:border-0">
							<div>
								<span class="text-sm text-white">{p.name}</span>
								<span class="text-xs text-gray-500 ml-2 font-mono">{p.id.slice(0, 12)}</span>
							</div>
							<button
								onclick={() => addAccess(p.id)}
								disabled={addingId === p.id}
								class="text-xs px-2 py-0.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded ml-2 flex items-center gap-1"
							>
								{#if addingId === p.id}
									<svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
									</svg>
									추가 중…
								{:else}
									추가
								{/if}
							</button>
						</div>
					{/each}
				</div>
			{:else if projectSearch.trim().length > 0}
				<div class="absolute z-10 left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-500">
					일치하는 프로젝트가 없습니다
				</div>
			{/if}
		</div>
	</div>

	<div class="text-sm text-gray-400 mb-2">접근 권한이 있는 프로젝트</div>
	{#if accessLoading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else if accessList.length === 0}
		<div class="text-gray-600 text-sm">접근 권한이 없습니다</div>
	{:else}
		<div class="space-y-2">
			{#each accessList as a (a.project_id)}
				<div class="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
					<div>
						<div class="text-xs text-gray-200">{a.project_name || a.project_id}</div>
						{#if a.project_name}
							<div class="text-xs text-gray-600 font-mono">{a.project_id.slice(0, 12)}</div>
						{/if}
					</div>
					<button onclick={() => removeAccess(a.project_id)} class="text-red-400 hover:text-red-300 text-xs">제거</button>
				</div>
			{/each}
		</div>
	{/if}
{/if}
