<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import SystemAdminTable from '$lib/components/admin/system-admins/SystemAdminTable.svelte';
	import SystemAdminGrantModal from '$lib/components/admin/system-admins/SystemAdminGrantModal.svelte';
	import SecurityPolicyBanner from '$lib/components/admin/system-admins/SecurityPolicyBanner.svelte';
	import MigrateModal from '$lib/components/admin/system-admins/MigrateModal.svelte';

	interface SystemAdmin {
		user_id: string;
		name: string;
		email: string;
		enabled: boolean;
	}

	interface SecurityPolicy {
		legacy_compat: boolean;
		system_admin_count: number;
		admin_project_member_count: number;
	}

	let admins = $state<SystemAdmin[]>([]);
	let policy = $state<SecurityPolicy | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let showGrant = $state(false);
	let showMigrate = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (admins.length === 0) loading = true;
		else refreshing = true;
		try {
			[admins, policy] = await Promise.all([
				api.get<SystemAdmin[]>('/api/v1/admin/identity/system-roles', token, projectId),
				api.get<SecurityPolicy>('/api/v1/admin/identity/security-policy', token, projectId),
			]);
		} catch {
			admins = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-system-admins',
		defaultActive: true,
		defaultInterval: 60,
		intervalOptions: [30, 60],
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="IDENTITY / SYSTEM ADMINS" title="시스템 관리자">
		{#snippet actions()}
			<button
				onclick={() => (showGrant = true)}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg"
			>
				+ 추가
			</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	{#if loading}
		<LoadingSkeleton variant="table" rows={3} />
	{:else}
			{#if policy}
				<SecurityPolicyBanner {policy} onMigrate={() => (showMigrate = true)} />
			{/if}

			{#if admins.length === 0}
				<div class="text-gray-500 text-sm py-12 text-center">
					등록된 system admin이 없습니다.
				</div>
			{:else}
				<SystemAdminTable {admins} onRevoked={load} />
			{/if}
	{/if}
</div>

{#if showGrant}
	<SystemAdminGrantModal onClose={() => (showGrant = false)} onGranted={load} />
{/if}

{#if showMigrate && policy}
	<MigrateModal
		adminProjectMemberCount={policy.admin_project_member_count}
		onClose={() => (showMigrate = false)}
		onMigrated={load}
	/>
{/if}
