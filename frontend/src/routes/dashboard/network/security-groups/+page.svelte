<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { untrack } from 'svelte';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import RefreshButton from '$lib/components/RefreshButton.svelte';

	interface SecurityGroupRule {
		id: string;
		direction: string;
		protocol: string | null;
		port_range_min: number | null;
		port_range_max: number | null;
		remote_ip_prefix: string | null;
		ethertype: string;
	}

	interface SecurityGroup {
		id: string;
		name: string;
		description: string;
		rules: SecurityGroupRule[];
	}

	let securityGroups = $state<SecurityGroup[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let sgError = $state('');

	let showSgModal = $state(false);
	let sgForm = $state({ name: '', description: '' });
	let expandedSg = $state<string | null>(null);
	let showAddRuleFor = $state<string | null>(null);
	let ruleForm = $state({ direction: 'ingress', protocol: '', port_range_min: '', port_range_max: '', remote_ip_prefix: '', ethertype: 'IPv4' });
	let sgCreating = $state(false);
	let sgCreateError = $state('');

	async function fetchSecurityGroups(opts?: { refresh?: boolean }) {
		try {
			securityGroups = await api.get<SecurityGroup[]>('/api/security-groups', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
			sgError = '';
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
		untrack(() => { fetchSecurityGroups(); });
		const interval = setInterval(() => untrack(() => { fetchSecurityGroups(); }), 30000);
		return () => clearInterval(interval);
	});
</script>

<div class="max-w-5xl mx-auto px-6 py-8">
	<!-- 헤더 -->
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-xl font-semibold text-white">보안 그룹</h1>
		<div class="flex items-center gap-2">
			<RefreshButton {refreshing} onclick={forceRefresh} />
			<button
				onclick={() => { showSgModal = true; sgCreateError = ''; }}
				class="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
			>+ 보안 그룹 생성</button>
		</div>
	</div>

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
		<div class="space-y-3">
			{#each securityGroups as sg (sg.id)}
				<div class="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden">
					<!-- SG 헤더 -->
					<div class="flex items-center gap-3 px-4 py-3">
						<button
							onclick={() => expandedSg = expandedSg === sg.id ? null : sg.id}
							class="flex items-center gap-2 flex-1 text-left min-w-0"
						>
							<span class="text-sm font-medium text-white truncate">{sg.name}</span>
							{#if sg.description}
								<span class="text-xs text-gray-500 truncate">{sg.description}</span>
							{/if}
							<span class="text-xs text-gray-600 ml-auto shrink-0">{sg.rules.length}개 규칙 {expandedSg === sg.id ? '▾' : '▸'}</span>
						</button>
						<button
							onclick={() => { showAddRuleFor = showAddRuleFor === sg.id ? null : sg.id; sgCreateError = ''; }}
							class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors shrink-0"
						>+ 규칙</button>
						<button
							onclick={() => deleteSecurityGroup(sg.id, sg.name)}
							class="text-xs text-red-400 hover:text-red-300 px-2 py-1 border border-red-900 hover:border-red-700 rounded transition-colors shrink-0"
						>삭제</button>
					</div>

					<!-- 규칙 추가 폼 -->
					{#if showAddRuleFor === sg.id}
						<div class="px-4 pb-3 border-t border-gray-700 pt-3 bg-gray-900/30">
							<p class="text-xs text-gray-500 mb-2">규칙 추가</p>
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
								<button onclick={() => addSgRule(sg.id)} disabled={sgCreating}
									class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600">
									{sgCreating ? '추가 중...' : '추가'}
								</button>
								<button onclick={() => { showAddRuleFor = null; sgCreateError = ''; }}
									class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 rounded transition-colors">취소</button>
							</div>
						</div>
					{/if}

					<!-- 규칙 목록 -->
					{#if expandedSg === sg.id}
						<div class="border-t border-gray-700">
							{#if sg.rules.length === 0}
								<p class="text-xs text-gray-600 px-4 py-3 italic">규칙 없음</p>
							{:else}
								<table class="w-full text-xs">
									<thead>
										<tr class="text-gray-600 uppercase tracking-wide border-b border-gray-700/50">
											<th class="text-left px-4 py-2">방향</th>
											<th class="text-left px-4 py-2">프로토콜</th>
											<th class="text-left px-4 py-2">포트</th>
											<th class="text-left px-4 py-2">원격 IP</th>
											<th class="text-right px-4 py-2"></th>
										</tr>
									</thead>
									<tbody>
										{#each sg.rules as rule (rule.id)}
											<tr class="border-b border-gray-800/50 hover:bg-gray-800/30">
												<td class="px-4 py-2 text-gray-400">{rule.direction === 'ingress' ? '인바운드' : '아웃바운드'}</td>
												<td class="px-4 py-2 text-gray-300 font-mono">{rule.protocol?.toUpperCase() ?? 'ANY'}</td>
												<td class="px-4 py-2 text-gray-400 font-mono">
													{#if rule.port_range_min != null && rule.port_range_max != null}
														{rule.port_range_min === rule.port_range_max ? rule.port_range_min : `${rule.port_range_min}-${rule.port_range_max}`}
													{:else}-{/if}
												</td>
												<td class="px-4 py-2 text-gray-400 font-mono">{rule.remote_ip_prefix ?? '-'}</td>
												<td class="px-4 py-2 text-right">
													<button onclick={() => deleteSgRule(sg.id, rule.id)}
														class="text-red-400 hover:text-red-300 transition-colors">✕</button>
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
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
