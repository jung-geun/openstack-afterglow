<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { siteConfig } from '$lib/config/site';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import ServiceTabs from '$lib/components/admin/services/ServiceTabs.svelte';
	import ServiceTabPanel from '$lib/components/admin/services/ServiceTabPanel.svelte';
	import type { Service, NetworkAgent, EndpointGroup, StoragePool, TabKey } from '$lib/types/adminServices';

	let computeServices = $state<Service[]>([]);
	let blockStorageServices = $state<Service[]>([]);
	let networkAgents = $state<NetworkAgent[]>([]);
	let sharedFsServices = $state<Service[]>([]);
	let orchestrationServices = $state<Service[]>([]);
	let containerServices = $state<Service[]>([]);
	let magnumServices = $state<Service[]>([]);
	let endpoints = $state<EndpointGroup[]>([]);
	let storagePools = $state<StoragePool[]>([]);

	const allCategories: TabKey[] = ['compute', 'network', 'block_storage', 'shared_file_system', 'orchestration', 'container', 'container_infra', 'endpoints', 'storage_pools'];

	const serviceTabMap: Partial<Record<TabKey, keyof NonNullable<typeof $siteConfig>['services']>> = {
		container_infra: 'magnum',
		shared_file_system: 'manila',
		container: 'zun',
	};

	let loadingMap = $state<Record<TabKey, boolean>>(Object.fromEntries(allCategories.map(c => [c, true])) as Record<TabKey, boolean>);
	let activeTab = $state<TabKey>('compute');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const tabs: { key: TabKey; label: string; count: () => number }[] = [
		{ key: 'compute', label: 'Compute', count: () => computeServices.length },
		{ key: 'network', label: 'Network', count: () => networkAgents.length },
		{ key: 'block_storage', label: 'Block Storage', count: () => blockStorageServices.length },
		{ key: 'shared_file_system', label: 'File Storage', count: () => sharedFsServices.length },
		{ key: 'orchestration', label: 'Orchestrator', count: () => orchestrationServices.length },
		{ key: 'container', label: 'Container', count: () => containerServices.length },
		{ key: 'container_infra', label: 'Magnum', count: () => magnumServices.length },
		{ key: 'endpoints', label: 'API Endpoints', count: () => endpoints.length },
		{ key: 'storage_pools', label: 'Storage Pools', count: () => storagePools.length },
	];

	let visibleTabs = $derived(
		tabs.filter(tab => {
			const serviceKey = serviceTabMap[tab.key];
			if (!serviceKey) return true;
			return ($siteConfig?.services as Record<string, boolean>)?.[serviceKey] ?? false;
		})
	);

	let activeCategories = $derived(
		allCategories.filter(cat => {
			const serviceKey = serviceTabMap[cat];
			if (!serviceKey) return true;
			return ($siteConfig?.services as Record<string, boolean>)?.[serviceKey] ?? false;
		})
	);

	async function loadCategory(cat: TabKey, isRefresh = false) {
		if (!isRefresh) loadingMap[cat] = true;
		try {
			const url = isRefresh ? `/api/v1/admin/services?category=${cat}&refresh=true` : `/api/v1/admin/services?category=${cat}`;
			const res = await api.get<Record<string, unknown>>(url, token, projectId);
			switch (cat) {
				case 'compute': computeServices = (res.compute as Service[]) || []; break;
				case 'block_storage': blockStorageServices = (res.block_storage as Service[]) || []; break;
				case 'network': networkAgents = (res.network as NetworkAgent[]) || []; break;
				case 'shared_file_system': sharedFsServices = (res.shared_file_system as Service[]) || []; break;
				case 'orchestration': orchestrationServices = (res.orchestration as Service[]) || []; break;
				case 'container': containerServices = (res.container as Service[]) || []; break;
				case 'container_infra': magnumServices = (res.container_infra as Service[]) || []; break;
				case 'endpoints': endpoints = (res.endpoints as EndpointGroup[]) || []; break;
				case 'storage_pools': storagePools = (res.storage_pools as StoragePool[]) || []; break;
			}
		} catch {
			// 조회 실패 시 빈 배열 유지
		} finally {
			loadingMap[cat] = false;
		}
	}

	function loadAll(isRefresh = false) { activeCategories.forEach(cat => loadCategory(cat, isRefresh)); }
	function refresh() { loadAll(true); }

	$effect(() => {
		if (visibleTabs.length > 0 && !visibleTabs.find(t => t.key === activeTab)) {
			activeTab = visibleTabs[0].key;
		}
	});

	const ar = createAutoRefresh(() => { loadAll(true); }, {
		storageKey: 'admin-services',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	onMount(() => { loadAll(); });
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="SYSTEM / SERVICES" title="서비스 상태">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				onManualRefresh={refresh}
			/>
		{/snippet}
	</PageHeader>

	<ServiceTabs
		tabs={visibleTabs.map(t => ({ key: t.key, label: t.label, count: t.count() }))}
		bind:activeTab
		{loadingMap}
	/>

	<ServiceTabPanel
		{activeTab}
		{computeServices}
		{blockStorageServices}
		{networkAgents}
		{sharedFsServices}
		{orchestrationServices}
		{containerServices}
		{magnumServices}
		{endpoints}
		{storagePools}
		{loadingMap}
	/>
</div>
