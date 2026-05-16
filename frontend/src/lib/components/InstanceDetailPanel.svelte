<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { createInstanceDetailStore, provideInstanceDetail } from '$lib/stores/instanceDetail.svelte';
	import InstanceHeader from '$lib/components/instance/InstanceHeader.svelte';
	import InfoSection from '$lib/components/instance/InfoSection.svelte';
	import MetricsPanel from '$lib/components/instance/MetricsPanel.svelte';
	import ConsoleSection from '$lib/components/instance/ConsoleSection.svelte';
	import NetworkSection from '$lib/components/instance/NetworkSection.svelte';
	import VolumesSection from '$lib/components/instance/VolumesSection.svelte';
	import UnionInfoSection from '$lib/components/instance/UnionInfoSection.svelte';
	import MigrateModal from '$lib/components/instance/MigrateModal.svelte';
	import PasswordModal from '$lib/components/instance/PasswordModal.svelte';
	import ResizeModal from '$lib/components/instance/ResizeModal.svelte';

	interface Props {
		instanceId: string;
		onClose?: () => void;
		adminProjectId?: string | null;
	}

	let { instanceId, onClose, adminProjectId = null }: Props = $props();

	const s = createInstanceDetailStore({
		instanceId: () => instanceId,
		effectiveProjectId: () => adminProjectId ?? ($auth.projectId ?? undefined),
		adminMode: () => !!adminProjectId,
		onDelete: () => {
			if (onClose) onClose();
			else goto('/dashboard/compute/instances');
		},
	});

	provideInstanceDetail(s);

	// Modal control
	let showMigrateModal = $state(false);
	let migrateType = $state<'live' | 'cold'>('live');
	let showPasswordModal = $state(false);
	let showResizeModal = $state(false);

	$effect(() => {
		if (!instanceId || !$auth.token) return;
		s.fetchInstance(instanceId);
	});

	async function openMigrateModal(type: 'live' | 'cold') {
		migrateType = type;
		s.migrateError = '';
		showMigrateModal = true;
		await s.loadMigrateHosts();
	}

	function openPasswordModal() {
		showPasswordModal = true;
	}

	async function openResizeModal() {
		s.resizeError = '';
		showResizeModal = true;
		await s.loadResizeFlavors();
	}
</script>

<div class="p-8">
	<div class="mb-6 flex items-center justify-between">
		{#if onClose}
			<button onclick={onClose} class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
				✕ 닫기
			</button>
		{:else}
			<a href="/dashboard/compute/instances" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
				← 인스턴스
			</a>
		{/if}
		<AutoRefreshControl
			bind:active={s.detailPollAr.active}
			bind:intervalSeconds={s.detailPollAr.intervalSeconds}
			intervalOptions={s.detailPollAr.intervalOptions}
			refreshing={s.refreshing}
			onManualRefresh={s.manualRefresh}
		/>
	</div>

	{#if s.error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{s.error}
		</div>
	{:else if s.loading}
		<LoadingSkeleton variant="card" rows={6} />
	{:else if s.instance}
		<InstanceHeader
			{adminProjectId}
			onOpenMigrateModal={openMigrateModal}
			onOpenPasswordModal={openPasswordModal}
			onOpenResizeModal={openResizeModal}
		/>
		<InfoSection />
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="text-white text-[15px] font-semibold mb-4">성능 모니터링</div>
			<MetricsPanel
				instanceId={s.instance.id}
				isGpu={(s.instance.flavor_name ?? '').toLowerCase().startsWith('gpu.')}
			/>
		</div>
		<ConsoleSection />
		<NetworkSection />
		<VolumesSection />
		<UnionInfoSection />
	{/if}
</div>

{#if showMigrateModal}
	<MigrateModal type={migrateType} onClose={() => { showMigrateModal = false; }} />
{/if}
{#if showPasswordModal}
	<PasswordModal onClose={() => { showPasswordModal = false; }} />
{/if}
{#if showResizeModal}
	<ResizeModal onClose={() => { showResizeModal = false; }} />
{/if}
