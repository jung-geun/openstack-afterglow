<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import type { SecurityGroup } from '$lib/types/resources';
	import SecurityGroupList from '$lib/components/dashboard/network/security-groups/SecurityGroupList.svelte';
	import SecurityGroupRulesPanel from '$lib/components/dashboard/network/security-groups/SecurityGroupRulesPanel.svelte';
	import SecurityGroupCreateModal from '$lib/components/dashboard/network/security-groups/SecurityGroupCreateModal.svelte';

	let securityGroups = $state<SecurityGroup[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let sgError = $state('');

	let showSgModal = $state(false);
	let selectedSg = $state<string | null>(null);
	let addRuleOpen = $state(false);
	let ruleForm = $state({ direction: 'ingress', protocol: '', port_range_min: '', port_range_max: '', remote_ip_prefix: '', ethertype: 'IPv4' });
	let sgCreating = $state(false);
	let sgCreateError = $state('');

	let curSg = $derived(securityGroups.find(sg => sg.name === selectedSg) ?? null);

	async function fetchSecurityGroups(opts?: { refresh?: boolean }) {
		try {
			securityGroups = await api.get<SecurityGroup[]>('/api/security-groups', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
			sgError = '';
			if (!selectedSg && securityGroups.length > 0) {
				selectedSg = securityGroups[0].name;
			}
		} catch (e) {
			sgError = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchSecurityGroups({ refresh: true });
		} finally {
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(() => fetchSecurityGroups(), {
		storageKey: 'dashboard-network-sg',
		defaultActive: true,
		defaultInterval: 60,
		intervalOptions: [10, 15, 30, 60],
	});

	async function createSecurityGroup(form: { name: string; description: string }): Promise<boolean> {
		if (!form.name.trim()) return false;
		sgCreating = true;
		sgCreateError = '';
		try {
			await api.post('/api/security-groups', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showSgModal = false;
			await fetchSecurityGroups();
			return true;
		} catch (e) {
			sgCreateError = e instanceof ApiError ? e.message : '생성 실패';
			return false;
		} finally {
			sgCreating = false;
		}
	}

	async function deleteSecurityGroup(sgId: string, name: string) {
		if (!await confirmDialog(`"${name}" 보안 그룹을 삭제하시겠습니까?`)) return;
		try {
			await api.delete(`/api/security-groups/${sgId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			if (selectedSg === name) selectedSg = null;
			await fetchSecurityGroups();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	async function addSgRule(sgId: string) {
		sgCreating = true;
		sgCreateError = '';
		try {
			const body: Record<string, unknown> = {
				direction: ruleForm.direction,
				ethertype: ruleForm.ethertype,
			};
			if (ruleForm.protocol) body.protocol = ruleForm.protocol;
			if (ruleForm.port_range_min) body.port_range_min = parseInt(ruleForm.port_range_min);
			if (ruleForm.port_range_max) body.port_range_max = parseInt(ruleForm.port_range_max);
			if (body.port_range_min != null && body.port_range_max == null) body.port_range_max = body.port_range_min;
			if (ruleForm.remote_ip_prefix) body.remote_ip_prefix = ruleForm.remote_ip_prefix;
			await api.post(`/api/security-groups/${sgId}/rules`, body, $auth.token ?? undefined, $auth.projectId ?? undefined);
			addRuleOpen = false;
			ruleForm = { direction: 'ingress', protocol: '', port_range_min: '', port_range_max: '', remote_ip_prefix: '', ethertype: 'IPv4' };
			await fetchSecurityGroups();
		} catch (e) {
			sgCreateError = e instanceof ApiError ? e.message : '규칙 추가 실패';
		} finally {
			sgCreating = false;
		}
	}

	async function deleteSgRule(sgId: string, ruleId: string) {
		try {
			await api.delete(`/api/security-groups/${sgId}/rules/${ruleId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchSecurityGroups();
		} catch (e) {
			alert('규칙 삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		untrack(() => fetchSecurityGroups());
	});
</script>

<div class="p-4 md:p-8">
	<PageHeader breadcrumb="NETWORK / SECURITY GROUPS" title="보안 그룹">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing}
				onManualRefresh={forceRefresh}
			/>
			<button
				onclick={() => { showSgModal = true; sgCreateError = ''; }}
				class="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
			>+ 보안 그룹 생성</button>
		{/snippet}
	</PageHeader>

	<!-- 에러 -->
	{#if sgError}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{sgError}</div>
	{/if}

	<!-- 목록 -->
	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if securityGroups.length === 0}
		<div class="text-center py-20 text-gray-600">
			<div class="text-5xl mb-4">🔒</div>
			<div class="text-lg">보안 그룹이 없습니다</div>
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-[280px_1fr] gap-3.5 items-start">
			<SecurityGroupList groups={securityGroups} bind:selectedSg />

			{#if curSg}
				<SecurityGroupRulesPanel
					group={curSg}
					bind:addRuleOpen
					addingRule={sgCreating}
					addError={sgCreateError}
					bind:ruleForm
					onAddRule={() => addSgRule(curSg!.id)}
					onDeleteRule={(ruleId) => deleteSgRule(curSg!.id, ruleId)}
					onDeleteGroup={() => deleteSecurityGroup(curSg!.id, curSg!.name)}
					onCloseMobile={() => selectedSg = null}
				/>
			{:else}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex items-center justify-center text-gray-600 text-sm min-h-[200px]">
					왼쪽에서 보안 그룹을 선택하세요
				</div>
			{/if}
		</div>
	{/if}
</div>

<SecurityGroupCreateModal
	bind:open={showSgModal}
	creating={sgCreating}
	error={sgCreateError}
	onCreate={createSecurityGroup}
/>
