<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import type { SecurityGroup } from '$lib/types/resources';

	let securityGroups = $state<SecurityGroup[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let sgError = $state('');

	let showSgModal = $state(false);
	let sgForm = $state({ name: '', description: '' });
	let selectedSg = $state<string | null>(null);
	let showAddRuleFor = $state<string | null>(null);
	let ruleForm = $state({ direction: 'ingress', protocol: '', port_range_min: '', port_range_max: '', remote_ip_prefix: '', ethertype: 'IPv4' });
	let sgCreating = $state(false);
	let sgCreateError = $state('');

	let curSg = $derived(securityGroups.find(sg => sg.name === selectedSg) ?? null);

	async function fetchSecurityGroups(opts?: { refresh?: boolean }) {
		try {
			securityGroups = await api.get<SecurityGroup[]>('/api/security-groups', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
			sgError = '';
			// Initialize selectedSg to first group if not set
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

	async function createSecurityGroup() {
		if (!sgForm.name.trim()) return;
		sgCreating = true;
		sgCreateError = '';
		try {
			await api.post('/api/security-groups', sgForm, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showSgModal = false;
			sgForm = { name: '', description: '' };
			await fetchSecurityGroups();
		} catch (e) {
			sgCreateError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			sgCreating = false;
		}
	}

	async function deleteSecurityGroup(sgId: string, name: string) {
		if (!confirm(`"${name}" 보안 그룹을 삭제하시겠습니까?`)) return;
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
			showAddRuleFor = null;
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
			<!-- Left panel: SG list -->
			<div class="flex flex-col gap-2">
				{#each securityGroups as sg (sg.id)}
					<div
						onclick={() => selectedSg = sg.name}
						onkeydown={(e) => e.key === 'Enter' && (selectedSg = sg.name)}
						tabindex="0"
						role="button"
						class="p-3.5 rounded-[10px] border cursor-pointer transition-colors
							{selectedSg === sg.name ? 'bg-blue-600/10 border-blue-800' : 'bg-[#0B1220] border-gray-800 hover:border-gray-700'}"
					>
						<div class="flex items-center gap-2">
							<!-- Shield icon -->
							<div class="shrink-0 w-6 h-6 rounded-md {selectedSg === sg.name ? 'bg-blue-500/20 border border-blue-500/40' : 'bg-gray-800 border border-gray-700'} flex items-center justify-center">
								<svg class="w-3 h-3 {selectedSg === sg.name ? 'text-blue-400' : 'text-gray-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
								</svg>
							</div>
							<div class="text-white font-medium text-[13px] font-mono truncate">{sg.name}</div>
							<span class="ml-auto text-[11px] text-gray-500 shrink-0">{sg.rules?.length ?? 0}</span>
						</div>
						{#if sg.description}
							<div class="text-[11px] text-gray-400 mt-1.5 leading-snug truncate">{sg.description}</div>
						{/if}
					</div>
				{/each}
			</div>

			<!-- Right panel: selected SG rules -->
			{#if curSg}
				<!-- 모바일: 전체화면 오버레이 / 데스크톱: 인라인 -->
				<div class="fixed inset-0 z-50 bg-gray-950 overflow-y-auto p-4 sm:static sm:inset-auto sm:z-auto sm:bg-gray-900 sm:border sm:border-gray-800 sm:rounded-2xl sm:p-5 sm:overflow-visible">
					<div class="flex items-center mb-3.5">
						<button onclick={() => selectedSg = null} class="sm:hidden mr-2 text-gray-400 hover:text-white p-1">
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
						</button>
						<div>
							<div class="text-white text-[15px] font-semibold font-mono">{curSg.name}</div>
							{#if curSg.description}
								<div class="text-[11px] text-gray-500 mt-0.5">{curSg.description}</div>
							{/if}
						</div>
						<div class="ml-auto flex gap-2">
							<button
								onclick={() => deleteSecurityGroup(curSg!.id, curSg!.name)}
								class="px-3 py-1.5 text-[13px] text-red-400 hover:text-red-300 border border-red-900 hover:border-red-700 rounded-lg transition-colors"
							>삭제</button>
							<button
								onclick={() => { showAddRuleFor = showAddRuleFor === curSg!.id ? null : curSg!.id; sgCreateError = ''; }}
								class="px-3 py-1.5 text-[13px] bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors"
							>+ 규칙 추가</button>
						</div>
					</div>

					<!-- Add rule form -->
					{#if showAddRuleFor === curSg.id}
						<div class="mb-4 p-3.5 bg-[#0B1220] border border-gray-800 rounded-[10px]">
							<p class="text-xs text-gray-500 mb-2.5">규칙 추가</p>
							<div class="grid grid-cols-2 gap-2 mb-2 md:grid-cols-4">
								<select bind:value={ruleForm.direction}
									class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500">
									<option value="ingress">인바운드</option>
									<option value="egress">아웃바운드</option>
								</select>
								<select bind:value={ruleForm.ethertype}
									class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500">
									<option value="IPv4">IPv4</option>
									<option value="IPv6">IPv6</option>
								</select>
								<select bind:value={ruleForm.protocol}
									class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500">
									<option value="">전체 (Any)</option>
									<option value="tcp">TCP</option>
									<option value="udp">UDP</option>
									<option value="icmp">ICMP</option>
								</select>
								<input bind:value={ruleForm.remote_ip_prefix} placeholder="원격 IP (예: 0.0.0.0/0)"
									class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none" />
							</div>
							{#if ruleForm.protocol === 'tcp' || ruleForm.protocol === 'udp'}
								<div class="grid grid-cols-2 gap-2 mb-2 max-w-xs">
									<input bind:value={ruleForm.port_range_min} placeholder="시작 포트"
										class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none" />
									<input bind:value={ruleForm.port_range_max} placeholder="끝 포트"
										class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none" />
								</div>
							{/if}
							{#if sgCreateError}
								<p class="text-xs text-red-400 mb-2">{sgCreateError}</p>
							{/if}
							<div class="flex gap-2">
								<button onclick={() => addSgRule(curSg!.id)} disabled={sgCreating}
									class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600">
									{sgCreating ? '추가 중...' : '추가'}
								</button>
								<button onclick={() => { showAddRuleFor = null; sgCreateError = ''; }}
									class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 rounded transition-colors">취소</button>
							</div>
						</div>
					{/if}

					<!-- Rules table -->
					{#if curSg.rules.length === 0}
						<div class="text-center py-10 text-gray-600 text-sm">규칙이 없습니다</div>
					{:else}
						<div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
							<div class="grid grid-cols-[120px_120px_1fr_1.4fr_80px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
								<div>방향</div>
								<div>프로토콜</div>
								<div>포트</div>
								<div>출발지/대상</div>
								<div></div>
							</div>
							{#each curSg.rules as rule, i (rule.id)}
								<div class="grid grid-cols-[120px_120px_1fr_1.4fr_80px] px-4 py-3 text-[13px] items-center {i < curSg.rules.length - 1 ? 'border-b border-gray-800' : ''}">
									<div>
										<span class="text-[11px] px-2 py-0.5 rounded-md border font-medium
											{rule.direction === 'ingress' ? 'bg-emerald-900/25 border-emerald-800 text-emerald-400' : 'bg-blue-900/25 border-blue-800 text-blue-400'}">
											{rule.direction === 'ingress' ? '↓ ingress' : '↑ egress'}
										</span>
									</div>
									<div class="text-gray-200 font-mono text-xs uppercase">{rule.protocol ?? 'any'}</div>
									<div class="text-gray-200 font-mono text-xs">
										{rule.port_range_min
											? rule.port_range_min + (rule.port_range_max !== rule.port_range_min ? '-' + rule.port_range_max : '')
											: '—'}
									</div>
									<div class="text-gray-400 font-mono text-xs">{rule.remote_ip_prefix ?? '0.0.0.0/0'}</div>
									<div class="text-right">
										<button
											onclick={() => deleteSgRule(curSg!.id, rule.id)}
											class="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-900 hover:border-red-700 transition-colors"
										>제거</button>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{:else}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex items-center justify-center text-gray-600 text-sm min-h-[200px]">
					왼쪽에서 보안 그룹을 선택하세요
				</div>
			{/if}
		</div>
	{/if}
</div>

<!-- 보안그룹 생성 모달 -->
{#if showSgModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { showSgModal = false; }}
		onkeydown={(e) => e.key === 'Escape' && (showSgModal = false)}
		role="dialog" aria-modal="true" tabindex="-1">
		<div class="bg-gray-800 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
			<h3 class="text-lg font-semibold text-white mb-4">보안 그룹 생성</h3>
			<div class="space-y-3 mb-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1">이름 *
						<input bind:value={sgForm.name} placeholder="보안 그룹 이름"
							class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none mt-1" />
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">설명
						<input bind:value={sgForm.description} placeholder="설명 (선택)"
							class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none mt-1" />
					</label>
				</div>
			</div>
			{#if sgCreateError}
				<p class="text-xs text-red-400 mb-3">{sgCreateError}</p>
			{/if}
			<div class="flex gap-2">
				<button onclick={createSecurityGroup} disabled={sgCreating || !sgForm.name.trim()}
					class="flex-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm py-2 rounded transition-colors">
					{sgCreating ? '생성 중...' : '생성'}
				</button>
				<button onclick={() => { showSgModal = false; }}
					class="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm py-2 rounded transition-colors">취소</button>
			</div>
		</div>
	</div>
{/if}
