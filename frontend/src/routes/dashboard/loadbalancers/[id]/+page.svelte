<script lang="ts">
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { createLoadbalancerDetailController } from '$lib/stores/loadbalancerDetailController.svelte';
	import LoadBalancerHeader from '$lib/components/dashboard/loadbalancers/id/LoadBalancerHeader.svelte';
	import LbListenerSection from '$lib/components/dashboard/loadbalancers/id/LbListenerSection.svelte';
	import LbPoolSection from '$lib/components/dashboard/loadbalancers/id/LbPoolSection.svelte';

	const ctrl = createLoadbalancerDetailController({
		lbId: () => $page.params.id!,
		token: () => $auth.token ?? undefined,
		projectId: () => $auth.projectId ?? undefined,
	});

	$effect(() => { if ($auth.projectId) ctrl.fetchAll(); });
	$effect(() => { ctrl.fetchPoolMembers(); });
</script>

<div class="max-w-4xl mx-auto px-4 py-8 text-gray-100">
	{#if ctrl.loading}
		<div class="text-gray-500">불러오는 중...</div>
	{:else if ctrl.error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{ctrl.error}</div>
	{:else if ctrl.lb}
		<LoadBalancerHeader
			lb={ctrl.lb}
			deleting={ctrl.saving}
			onDelete={ctrl.deleteLb}
		/>

		<LbListenerSection
			listeners={ctrl.listeners}
			pools={ctrl.pools}
			saving={ctrl.saving}
			error=""
			onAdd={ctrl.createListener}
			onDelete={ctrl.deleteListener}
		/>

		<LbPoolSection
			pools={ctrl.pools}
			selectedPoolId={ctrl.selectedPoolId}
			members={ctrl.selectedPoolMembers}
			membersLoading={ctrl.membersLoading}
			saving={ctrl.saving}
			error=""
			addingMember={ctrl.addingMember}
			addMemberError={ctrl.addMemberError}
			onAddPool={ctrl.createPool}
			onDeletePool={ctrl.deletePool}
			onSelectPool={ctrl.loadPoolMembers}
			onAddMember={ctrl.addMember}
			onRemoveMember={ctrl.removeMember}
		/>
	{/if}
</div>
