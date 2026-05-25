<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { ProjectManagerMember, ProjectInvitation } from '$lib/types/project';

	type Tab = 'members' | 'invitations';

	let activeTab = $state<Tab>('members');
	let projectId = $derived($auth.projectId ?? '');

	// ── 멤버 탭 ───────────────────────────────────────────────────────────────
	let members = $state<ProjectManagerMember[]>([]);
	let membersLoading = $state(false);
	let membersError = $state('');

	async function loadMembers() {
		if (!projectId) return;
		membersLoading = true;
		membersError = '';
		try {
			const data = await api.get<{ items: ProjectManagerMember[] }>(
				`/api/projects/${projectId}/members`,
				$auth.token ?? undefined
			);
			members = data.items;
		} catch (e) {
			membersError = e instanceof ApiError ? e.message : '멤버 목록 조회 실패';
		} finally {
			membersLoading = false;
		}
	}

	async function promoteManager(userId: string) {
		try {
			await api.post(`/api/projects/${projectId}/managers/${userId}`, {}, $auth.token ?? undefined);
			await loadMembers();
		} catch (e) {
			membersError = e instanceof ApiError ? e.message : '승격 실패';
		}
	}

	async function demoteManager(userId: string) {
		try {
			await api.delete(`/api/projects/${projectId}/managers/${userId}`, $auth.token ?? undefined);
			await loadMembers();
		} catch (e) {
			membersError = e instanceof ApiError ? e.message : '해제 실패';
		}
	}

	// ── 초대 탭 ───────────────────────────────────────────────────────────────
	let invitations = $state<ProjectInvitation[]>([]);
	let invitationsLoading = $state(false);
	let invitationsError = $state('');
	let inviteEmail = $state('');
	let inviteRole = $state('member');
	let inviting = $state(false);
	let inviteSuccess = $state('');

	async function loadInvitations() {
		if (!projectId) return;
		invitationsLoading = true;
		invitationsError = '';
		try {
			const data = await api.get<{ items: ProjectInvitation[] }>(
				`/api/projects/${projectId}/invitations`,
				$auth.token ?? undefined
			);
			invitations = data.items;
		} catch (e) {
			invitationsError = e instanceof ApiError ? e.message : '초대 목록 조회 실패';
		} finally {
			invitationsLoading = false;
		}
	}

	async function sendInvitation() {
		if (!inviteEmail.trim() || inviting) return;
		inviting = true;
		invitationsError = '';
		inviteSuccess = '';
		try {
			await api.post(
				`/api/projects/${projectId}/invitations`,
				{ email: inviteEmail.trim(), keystone_role: inviteRole },
				$auth.token ?? undefined
			);
			inviteEmail = '';
			inviteSuccess = '초대가 발송되었습니다.';
			await loadInvitations();
		} catch (e) {
			invitationsError = e instanceof ApiError ? e.message : '초대 발송 실패';
		} finally {
			inviting = false;
		}
	}

	async function revokeInvitation(invId: number) {
		try {
			await api.delete(
				`/api/projects/${projectId}/invitations/${invId}`,
				$auth.token ?? undefined
			);
			await loadInvitations();
		} catch (e) {
			invitationsError = e instanceof ApiError ? e.message : '초대 취소 실패';
		}
	}

	// ── 탭 전환 ───────────────────────────────────────────────────────────────
	$effect(() => {
		if (activeTab === 'members') loadMembers();
		else loadInvitations();
	});

	function statusLabel(status: string): string {
		const map: Record<string, string> = {
			pending: '대기 중',
			accepted: '수락됨',
			declined: '거절됨',
			expired: '만료됨',
			revoked: '취소됨',
			no_user: '미가입',
		};
		return map[status] ?? status;
	}

	function statusColor(status: string): string {
		if (status === 'accepted') return 'text-green-400 bg-green-500/10';
		if (status === 'pending') return 'text-yellow-400 bg-yellow-500/10';
		if (status === 'no_user') return 'text-gray-400 bg-gray-500/10';
		return 'text-red-400 bg-red-500/10';
	}

	function fmtDate(iso: string): string {
		return new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<div class="px-6 py-6 max-w-4xl">
	<h1 class="text-lg font-semibold text-white mb-1">프로젝트 설정</h1>
	<p class="text-sm text-gray-500 mb-6">{projectId}</p>

	<!-- 탭 -->
	<div class="flex gap-1 mb-6 border-b border-gray-800">
		<button
			onclick={() => (activeTab = 'members')}
			class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {activeTab === 'members' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-white'}"
		>
			멤버
		</button>
		<button
			onclick={() => (activeTab = 'invitations')}
			class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px {activeTab === 'invitations' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-white'}"
		>
			초대
		</button>
	</div>

	<!-- ── 멤버 탭 ─────────────────────────────────────────────────────────── -->
	{#if activeTab === 'members'}
		{#if membersError}
			<div class="text-sm text-red-400 mb-4">{membersError}</div>
		{/if}

		{#if membersLoading}
			<div class="space-y-2">
				{#each [1, 2, 3] as _}
					<div class="h-12 bg-gray-800 rounded-lg animate-pulse"></div>
				{/each}
			</div>
		{:else if members.length === 0}
			<div class="text-gray-500 text-sm text-center py-12">멤버가 없습니다.</div>
		{:else}
			<div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wide">
							<th class="text-left px-4 py-3">사용자</th>
							<th class="text-left px-4 py-3">이메일</th>
							<th class="text-left px-4 py-3">역할</th>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-800">
						{#each members as m (m.user_id)}
							<tr class="hover:bg-gray-800/40 transition-colors">
								<td class="px-4 py-3 font-medium text-white">{m.username || m.user_id}</td>
								<td class="px-4 py-3 text-gray-400">{m.email || '—'}</td>
								<td class="px-4 py-3">
									{#if m.is_manager}
										<span class="text-[11px] px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 font-medium">관리자</span>
									{:else}
										<span class="text-gray-500 text-xs">멤버</span>
									{/if}
								</td>
								<td class="px-4 py-3 text-right">
									{#if m.user_id !== $auth.userId}
										{#if m.is_manager}
											<button
												onclick={() => demoteManager(m.user_id)}
												class="text-xs text-gray-500 hover:text-red-400 transition-colors"
											>
												관리자 해제
											</button>
										{:else}
											<button
												onclick={() => promoteManager(m.user_id)}
												class="text-xs text-gray-500 hover:text-blue-400 transition-colors"
											>
												관리자 지정
											</button>
										{/if}
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- ── 초대 탭 ─────────────────────────────────────────────────────────── -->
	{#if activeTab === 'invitations'}
		<!-- 초대 발송 폼 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-5">
			<h3 class="text-sm font-medium text-white mb-3">새 초대 발송</h3>
			<div class="flex gap-2">
				<input
					bind:value={inviteEmail}
					type="email"
					placeholder="user@example.com"
					class="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
					onkeydown={(e) => e.key === 'Enter' && sendInvitation()}
				/>
				<select
					bind:value={inviteRole}
					class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
				>
					<option value="member">member</option>
					<option value="reader">reader</option>
				</select>
				<button
					onclick={sendInvitation}
					disabled={!inviteEmail.trim() || inviting}
					class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
				>
					{inviting ? '발송 중...' : '초대 발송'}
				</button>
			</div>
			{#if inviteSuccess}
				<div class="mt-2 text-xs text-green-400">{inviteSuccess}</div>
			{/if}
			{#if invitationsError}
				<div class="mt-2 text-xs text-red-400">{invitationsError}</div>
			{/if}
		</div>

		<!-- 초대 목록 -->
		{#if invitationsLoading}
			<div class="space-y-2">
				{#each [1, 2] as _}
					<div class="h-12 bg-gray-800 rounded-lg animate-pulse"></div>
				{/each}
			</div>
		{:else if invitations.length === 0}
			<div class="text-gray-500 text-sm text-center py-8">초대 내역이 없습니다.</div>
		{:else}
			<div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wide">
							<th class="text-left px-4 py-3">이메일</th>
							<th class="text-left px-4 py-3">역할</th>
							<th class="text-left px-4 py-3">상태</th>
							<th class="text-left px-4 py-3">만료일</th>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-800">
						{#each invitations as inv (inv.id)}
							<tr class="hover:bg-gray-800/40 transition-colors">
								<td class="px-4 py-3 font-medium text-white">{inv.invited_email}</td>
								<td class="px-4 py-3 text-gray-400">{inv.keystone_role}</td>
								<td class="px-4 py-3">
									<span class="text-[11px] px-2 py-0.5 rounded font-medium {statusColor(inv.status)}">
										{statusLabel(inv.status)}
									</span>
								</td>
								<td class="px-4 py-3 text-gray-500 text-xs">{fmtDate(inv.expires_at)}</td>
								<td class="px-4 py-3 text-right">
									{#if inv.status === 'pending'}
										<button
											onclick={() => revokeInvitation(inv.id)}
											class="text-xs text-gray-500 hover:text-red-400 transition-colors"
										>
											취소
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>
