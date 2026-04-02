<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Instance {
		id: string;
		name: string;
		status: string;
		image_name: string | null;
		flavor_name: string | null;
		ip_addresses: string[];
		created_at: string | null;
		union_libraries: string[];
		union_strategy: string | null;
	}

	let instances = $state<Instance[]>([]);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state<string | null>(null);
	let consoleUrl = $state('');
	let interval: ReturnType<typeof setInterval>;

	async function fetchInstances() {
		try {
			instances = await api.get<Instance[]>('/api/instances', $auth.token ?? undefined, $auth.projectId ?? undefined);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function deleteInstance(id: string, name: string) {
		if (!confirm(`"${name}" 인스턴스를 삭제하시겠습니까?\nManila share와 볼륨도 함께 삭제됩니다.`)) return;
		deleting = id;
		try {
			await api.delete(`/api/instances/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchInstances();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function openConsole(id: string) {
		try {
			const data = await api.get<{ url: string }>(`/api/instances/${id}/console`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			window.open(data.url, '_blank');
		} catch {
			alert('콘솔 URL을 가져올 수 없습니다');
		}
	}

	onMount(() => {
		fetchInstances();
		interval = setInterval(fetchInstances, 10000);
	});

	onDestroy(() => clearInterval(interval));

	const statusColor: Record<string, string> = {
		ACTIVE:   'text-green-400 bg-green-900/30',
		BUILD:    'text-yellow-400 bg-yellow-900/30',
		SHUTOFF:  'text-gray-400 bg-gray-800',
		ERROR:    'text-red-400 bg-red-900/30',
		DELETING: 'text-orange-400 bg-orange-900/30',
	};

	const strategyLabel: Record<string, string> = {
		prebuilt: '사전 빌드',
		dynamic:  '동적 생성',
	};
</script>

<div class="p-8">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">VM 인스턴스</h1>
		<a
			href="/create"
			class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
		>
			+ VM 생성
		</a>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
			{error}
		</div>
	{/if}

	{#if loading}
		<div class="text-gray-500 text-sm">불러오는 중...</div>
	{:else if instances.length === 0}
		<div class="text-center py-20 text-gray-600">
			<div class="text-5xl mb-4">☁️</div>
			<p class="text-lg">인스턴스가 없습니다</p>
			<a href="/create" class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
				첫 VM을 생성하세요 →
			</a>
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 pr-6">이름</th>
						<th class="text-left py-3 pr-6">상태</th>
						<th class="text-left py-3 pr-6">이미지</th>
						<th class="text-left py-3 pr-6">IP</th>
						<th class="text-left py-3 pr-6">라이브러리</th>
						<th class="text-left py-3 pr-6">전략</th>
						<th class="text-right py-3">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each instances as inst (inst.id)}
						<tr class="border-b border-gray-800/50 hover:bg-gray-900/30 transition-colors">
							<td class="py-3 pr-6 font-medium text-white">{inst.name}</td>
							<td class="py-3 pr-6">
								<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[inst.status] ?? 'text-gray-400 bg-gray-800'}">
									{inst.status}
								</span>
							</td>
							<td class="py-3 pr-6 text-gray-400">{inst.image_name ?? '-'}</td>
							<td class="py-3 pr-6 text-gray-400 font-mono text-xs">
								{inst.ip_addresses[0] ?? '-'}
							</td>
							<td class="py-3 pr-6">
								<div class="flex flex-wrap gap-1">
									{#each inst.union_libraries.filter(Boolean) as lib}
										<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{lib}</span>
									{/each}
								</div>
							</td>
							<td class="py-3 pr-6 text-gray-500 text-xs">
								{inst.union_strategy ? strategyLabel[inst.union_strategy] ?? inst.union_strategy : '-'}
							</td>
							<td class="py-3 text-right">
								<div class="flex items-center justify-end gap-2">
									{#if inst.status === 'ACTIVE'}
										<button
											onclick={() => openConsole(inst.id)}
											class="text-gray-400 hover:text-white text-xs px-2 py-1 rounded border border-gray-700 hover:border-gray-500 transition-colors"
										>
											콘솔
										</button>
									{/if}
									<button
										onclick={() => deleteInstance(inst.id, inst.name)}
										disabled={deleting === inst.id}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
									>
										{deleting === inst.id ? '삭제 중...' : '삭제'}
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
