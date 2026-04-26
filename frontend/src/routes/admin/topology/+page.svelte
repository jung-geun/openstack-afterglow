<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { projectNames } from '$lib/stores/projectNames';

	let isLight = $state(false);
	onMount(() => {
		isLight = document.documentElement.classList.contains('light');
		const obs = new MutationObserver(() => {
			isLight = document.documentElement.classList.contains('light');
		});
		obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => obs.disconnect();
	});

	interface SubnetDetail {
		id: string; name: string; cidr: string;
		gateway_ip: string | null; dhcp_enabled: boolean;
	}
	interface TopologyNetwork {
		id: string; name: string; status: string;
		is_external: boolean; is_shared: boolean;
		project_id: string | null;
		subnet_details: SubnetDetail[];
	}
	interface TopologyRouter {
		id: string; name: string; status: string;
		external_gateway_network_id: string | null;
		external_gateway_ips: string[];
		interface_ips: { ip_address: string; subnet_id: string }[];
		is_distributed: boolean;
		is_ha: boolean;
		connected_subnet_ids: string[];
		dvr_subnet_ids: string[];
		project_id: string | null;
	}
	interface TopologyInstance {
		id: string; name: string; status: string;
		project_id?: string | null;
		network_names: string[];
		ip_addresses: { addr: string; type: string; network_name: string }[];
	}
	interface FloatingIpInfo {
		id: string; floating_ip_address: string;
		fixed_ip_address: string | null; status: string;
		port_id: string | null; floating_network_id: string;
		project_id?: string | null;
	}
	interface TopologyData {
		networks: TopologyNetwork[];
		routers: TopologyRouter[];
		instances: TopologyInstance[];
		floating_ips: FloatingIpInfo[];
	}

	let data = $state<TopologyData | null>(null);
	let loading = $state(true);
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);

	// 프로젝트 필터
	let projectFilter = $state<string | null>(null);
	let projectSearchText = $state('');
	let projectDropdownOpen = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let projectSuggestions = $derived(
		Array.from($projectNames.entries())
			.filter(([id, name]) =>
				projectSearchText.length === 0 ||
				name.toLowerCase().includes(projectSearchText.toLowerCase()) ||
				id.toLowerCase().includes(projectSearchText.toLowerCase())
			)
			.slice(0, 10)
	);

	function handleDocumentClick(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.project-filter-wrapper')) {
			projectDropdownOpen = false;
		}
	}

	$effect(() => {
		if (!$auth.token) return;
		fetchTopology();
	});

	onMount(() => {
		projectNames.load(token, projectId);
		document.addEventListener('click', handleDocumentClick);
		return () => document.removeEventListener('click', handleDocumentClick);
	});

	async function fetchTopology() {
		loading = true;
		error = '';
		try {
			data = await api.get<TopologyData>(
				'/api/admin/topology',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}
</script>

<div class="p-4 md:p-8 max-w-screen-2xl mx-auto">
	<PageHeader breadcrumb="NETWORK / TOPOLOGY" title="토폴로지">
		{#snippet actions()}
			<button
				onclick={fetchTopology}
				disabled={loading}
				class="text-sm px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:text-gray-600 disabled:border-gray-800 transition-colors"
			>
				{loading ? '로딩 중…' : '새로고침'}
			</button>
		{/snippet}
	</PageHeader>

	<!-- 프로젝트 필터 -->
	<div class="flex gap-3 mb-4">
		<div class="relative project-filter-wrapper">
			<div class="flex items-center bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 w-52 focus-within:border-blue-500">
				<input
					type="text"
					placeholder="프로젝트 검색..."
					bind:value={projectSearchText}
					onfocus={() => (projectDropdownOpen = true)}
					oninput={() => { projectDropdownOpen = true; if (!projectSearchText) { projectFilter = null; } }}
					class="bg-transparent text-sm text-gray-300 flex-1 outline-none min-w-0"
				/>
				{#if projectFilter}
					<button onclick={() => { projectFilter = null; projectSearchText = ''; projectDropdownOpen = false; }} class="text-gray-500 hover:text-white ml-1 flex-shrink-0">✕</button>
				{/if}
			</div>
			{#if projectDropdownOpen && projectSuggestions.length > 0}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="absolute top-full mt-1 left-0 w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-20 overflow-hidden"
					onmouseleave={() => {}}
				>
					{#each projectSuggestions as [id, name]}
						<button
							class="w-full text-left px-3 py-2 text-xs hover:bg-gray-800 transition-colors {projectFilter === id ? 'bg-blue-900/30 text-blue-400' : 'text-gray-300'}"
							onclick={() => { projectFilter = id; projectSearchText = name; projectDropdownOpen = false; }}
						>
							<div class="font-medium truncate">{name}</div>
							<div class="text-gray-500 font-mono">{id.slice(0, 12)}...</div>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={8} />
	{:else if data}
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<GlobalTopology
				{data}
				projectId={projectFilter}
				showAll={projectFilter == null}
				onSelectInstance={(id) => { selectedInstanceId = id; }}
				onSelectRouter={(id) => { selectedRouterId = id; }}
			/>
		</div>

		<!-- 범례 -->
		<div class="flex flex-wrap gap-5 text-xs text-gray-400 px-1">
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-2 h-4 rounded" style="background:#ea580c"></span>
				외부 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-2 h-4 rounded" style="background:#0d9488"></span>
				공유 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-2 h-4 rounded" style="background:#3b82f6"></span>
				내부 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded-full" style="background:{isLight ? '#fffbeb' : '#1c1400'};border:1px solid #f59e0b"></span>
				라우터 (외부 게이트웨이)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded-full" style="background:{isLight ? '#f8fafc' : '#0f172a'};border:1px solid #64748b"></span>
				라우터 (내부)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#f0fdf4' : '#052e16'};border:1px solid #22c55e"></span>
				인스턴스 (ACTIVE)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#fef2f2' : '#450a0a'};border:1px solid #ef4444"></span>
				인스턴스 (SHUTOFF/ERROR)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#f8fafc' : '#1c1917'};border:1px solid #78716c"></span>
				인스턴스 (기타)
			</span>
		</div>

		<!-- 전체 요약 -->
		<div class="mt-4 flex gap-6 text-xs text-gray-500 px-1">
			<span>네트워크 {data.networks.length}개</span>
			<span>라우터 {data.routers.length}개</span>
			<span>인스턴스 {data.instances.length}개</span>
			<span>Floating IP {data.floating_ips.length}개</span>
		</div>
	{/if}
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={() => selectedInstanceId = null}>
		<InstanceDetailPanel instanceId={selectedInstanceId} onClose={() => selectedInstanceId = null} />
	</SlidePanel>
{/if}

{#if selectedRouterId}
	<SlidePanel onClose={() => selectedRouterId = null} width="w-full md:w-[60vw] max-w-3xl">
		<RouterDetailPanel routerId={selectedRouterId} onClose={() => selectedRouterId = null} />
	</SlidePanel>
{/if}
