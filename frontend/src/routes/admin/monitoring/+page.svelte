<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { SectionHeader } from '$lib/components/ui';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import MonitoringSummaryTab from '$lib/components/admin/monitoring/MonitoringSummaryTab.svelte';
	import InstanceMetricsTab from '$lib/components/admin/monitoring/InstanceMetricsTab.svelte';
	import type { MonitoringSummary } from '$lib/components/admin/monitoring/MonitoringSummaryTab.svelte';

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let tab = $state<'summary' | 'instances'>('summary');

	let summary = $state<MonitoringSummary | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);

	async function load() {
		if (!summary) loading = true;
		else refreshing = true;
		try {
			summary = await api.get<MonitoringSummary>('/api/admin/monitoring/summary', token, projectId);
		} catch {
			summary = null;
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-monitoring',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60]
	});

	let instancesLoading = $state(false);
	let refreshRef: (() => void) | undefined;
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="MONITORING" title="통합 모니터링">
		{#snippet actions()}
			{#if tab === 'summary'}
				<AutoRefreshControl
					bind:active={ar.active}
					bind:intervalSeconds={ar.intervalSeconds}
					intervalOptions={ar.intervalOptions}
					refreshing={loading || refreshing}
					onManualRefresh={load}
				/>
			{:else}
				<button
					onclick={() => refreshRef?.()}
					disabled={instancesLoading}
					class="text-xs px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-40 transition-colors"
				>
					{instancesLoading ? '로딩 중...' : '새로고침'}
				</button>
			{/if}
		{/snippet}
	</PageHeader>

	<div class="flex gap-1 mb-6 border-b border-gray-800">
		<button
			onclick={() => (tab = 'summary')}
			class="px-4 py-2 text-sm font-medium transition-colors -mb-px border-b-2
				{tab === 'summary' ? 'text-white border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-300'}"
		>클러스터 요약</button>
		<button
			onclick={() => (tab = 'instances')}
			class="px-4 py-2 text-sm font-medium transition-colors -mb-px border-b-2
				{tab === 'instances' ? 'text-white border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-300'}"
		>인스턴스 메트릭</button>
	</div>

	{#if tab === 'summary'}
		<MonitoringSummaryTab {summary} {loading} {refreshing} />
	{:else}
		<InstanceMetricsTab
			{token}
			{projectId}
			onReload={fn => (refreshRef = fn)}
			bind:loadingInstances={instancesLoading}
		/>
	{/if}

	<!-- Grafana 바로가기 -->
	<div class="mt-6 bg-gray-900 border border-gray-800 rounded-2xl p-5">
		<SectionHeader title="Grafana 대시보드" meta="빠른 접근" />
		<div class="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
			{#each [
				{ label: 'Node Exporter',  href: '/grafana/d/node-exporter' },
				{ label: 'Ceph',           href: '/grafana/d/ceph' },
				{ label: 'RabbitMQ',       href: '/grafana/d/rabbitmq' },
				{ label: 'MySQL/Galera',   href: '/grafana/d/mysql' },
				{ label: 'Memcached',      href: '/grafana/d/memcached' },
				{ label: 'HAProxy',        href: '/grafana/d/haproxy' },
				{ label: 'etcd',           href: '/grafana/d/etcd' },
				{ label: 'OpenStack',      href: '/grafana/d/openstack' },
				{ label: 'libvirt',        href: '/grafana/d/libvirt' },
			] as g}
				<a
					href={g.href}
					target="_blank"
					rel="noopener noreferrer"
					class="flex items-center gap-2 px-3 py-2 rounded-xl border text-xs transition-colors hover:border-[var(--admin-ring)] hover:text-[var(--admin-tone)]"
					style="background: var(--color-surface-canvas); border-color: var(--color-line); color: var(--color-ink-2);"
				>
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
						<polyline points="15 3 21 3 21 9"/>
						<line x1="10" y1="14" x2="21" y2="3"/>
					</svg>
					{g.label}
				</a>
			{/each}
		</div>
	</div>
</div>
