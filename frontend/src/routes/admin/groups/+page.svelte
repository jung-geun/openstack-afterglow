<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Group {
		id: string;
		name: string;
		description: string;
		domain_id: string | null;
	}
	interface GroupMember {
		id: string;
		name: string;
		email: string;
		enabled: boolean;
	}
	interface User {
		id: string;
		name: string;
	}

	let groups = $state<Group[]>([]);
	let loading = $state(true);
	let error = $state('');

	// 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let form = $state({ name: '', description: '' });

	// 수정 모달
	let editGroup = $state<Group | null>(null);
	let editName = $state('');
	let editDesc = $state('');
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deleteGroup = $state<Group | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	// 멤버 패널
	let expandedGroup = $state<string | null>(null);
	let groupMembers = $state<Record<string, GroupMember[]>>({});
	let membersLoading = $state<Record<string, boolean>>({});
	let allUsers = $state<User[]>([]);
	let addMemberUserId = $state('');
	let addMemberSearchText = $state('');
	let addMemberError = $state<Record<string, string>>({});
	let addMemberSaving = $state<Record<string, boolean>>({});

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true; error = '';
		try {
			const res = await api.get<Group[]>('/api/admin/groups', token, projectId);
			groups = res;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '그룹 목록 조회 실패';
		} finally { loading = false; }
	}

	async function loadUsers() {
		if (allUsers.length > 0) return;
		try {
			const res = await api.get<{ items: User[] }>('/api/admin/users?limit=100', token, projectId);
			allUsers = res.items;
		} catch {}
	}

	async function createGroup() {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/groups', { name: form.name, description: form.description || null }, token, projectId);
			showCreate = false; form = { name: '', description: '' }; await load();
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; } finally { creating = false; }
	}

	async function updateGroup() {
		if (!editGroup) return;
		updating = true; editError = '';
		try {
			await api.patch(`/api/admin/groups/${editGroup.id}`, { name: editName, description: editDesc || null }, token, projectId);
			editGroup = null; await load();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deleteGroup) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/groups/${deleteGroup.id}`, token, projectId);
			deleteGroup = null; await load();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	async function toggleMembers(g: Group) {
		if (expandedGroup === g.id) {
			expandedGroup = null;
			return;
		}
		expandedGroup = g.id;
		addMemberSearchText = '';
		await loadGroupMembers(g.id);
		await loadUsers();
	}

	async function loadGroupMembers(groupId: string) {
		membersLoading = { ...membersLoading, [groupId]: true };
		try {
			const res = await api.get<GroupMember[]>(`/api/admin/groups/${groupId}/users`, token, projectId);
			groupMembers = { ...groupMembers, [groupId]: res };
		} catch {
			groupMembers = { ...groupMembers, [groupId]: [] };
		} finally {
			membersLoading = { ...membersLoading, [groupId]: false };
		}
	}

	async function addMember(groupId: string, userId: string) {
		if (!userId) return;
		addMemberSaving = { ...addMemberSaving, [groupId]: true };
		addMemberError = { ...addMemberError, [groupId]: '' };
		try {
			await api.put(`/api/admin/groups/${groupId}/users/${userId}`, {}, token, projectId);
			addMemberSearchText = '';
			await loadGroupMembers(groupId);
		} catch (e) {
			addMemberError = { ...addMemberError, [groupId]: e instanceof ApiError ? e.message : '추가 실패' };
		} finally {
			addMemberSaving = { ...addMemberSaving, [groupId]: false };
		}
	}

	async function removeMember(groupId: string, userId: string) {
		try {
			await api.delete(`/api/admin/groups/${groupId}/users/${userId}`, token, projectId);
			try {
				await loadGroupMembers(groupId);
			} catch {
				// 그룹 멤버십 변경으로 Keystone 토큰이 무효화될 수 있음 — 페이지 새로고침
				window.location.reload();
			}
		} catch {}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-5xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">그룹 관리</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if groups.length === 0}
		<div class="text-center text-gray-500 text-sm py-8">그룹이 없습니다</div>
	{:else}
		<div class="space-y-2">
			{#each groups as g (g.id)}
				<div class="bg-gray-900 border border-gray-800 rounded-xl">
					<div class="flex items-center justify-between px-4 py-3">
						<div class="flex items-center gap-4 min-w-0">
							<div>
								<div class="text-sm font-medium text-white">{g.name}</div>
								<div class="text-xs text-gray-500">{g.description || '-'}</div>
							</div>
							<div class="text-xs text-gray-600 font-mono hidden sm:block">{g.id.slice(0, 8)}</div>
						</div>
						<div class="flex items-center gap-1 ml-4 shrink-0">
							<button onclick={() => toggleMembers(g)}
								class="px-2 py-0.5 text-xs {expandedGroup === g.id ? 'bg-blue-700 text-white' : 'bg-blue-900/40 text-blue-400'} hover:bg-blue-700 rounded transition-colors">멤버</button>
							<button onclick={() => { editGroup = g; editName = g.name; editDesc = g.description; editError = ''; }}
								class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">수정</button>
							<button onclick={() => { deleteGroup = g; deleteError = ''; }}
								class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
						</div>
					</div>

					{#if expandedGroup === g.id}
						<div class="border-t border-gray-800 bg-gray-900/50 px-4 py-4">
							{#if membersLoading[g.id]}
								<div class="text-xs text-gray-500 py-2">로딩 중...</div>
							{:else}
								<div class="text-xs text-gray-400 uppercase tracking-wide mb-2">멤버</div>
								{#if (groupMembers[g.id] ?? []).length === 0}
									<div class="text-xs text-gray-600 mb-3">멤버가 없습니다</div>
								{:else}
									<div class="space-y-1 mb-3">
										{#each groupMembers[g.id] ?? [] as m}
											<div class="flex items-center justify-between bg-gray-800/50 rounded px-3 py-1.5">
												<div>
													<span class="text-sm text-white">{m.name}</span>
													{#if m.email}<span class="text-xs text-gray-500 ml-2">{m.email}</span>{/if}
												</div>
												<button onclick={() => removeMember(g.id, m.id)} class="text-xs text-red-400 hover:text-red-300">제거</button>
											</div>
										{/each}
									</div>
								{/if}
								<div class="border-t border-gray-700/50 pt-3">
									{#if addMemberError[g.id]}
										<div class="text-xs text-red-400 mb-2">{addMemberError[g.id]}</div>
									{/if}
									<div class="text-xs text-gray-400 mb-2">사용자 검색</div>
									<div class="relative">
										<input
											type="text"
											placeholder="이름으로 검색하여 멤버 추가..."
											bind:value={addMemberSearchText}
											class="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
										/>
										{#if addMemberSearchText.trim().length > 0}
											{@const existingIds = new Set((groupMembers[g.id] ?? []).map(m => m.id))}
											{@const filtered = allUsers.filter(u => !existingIds.has(u.id) && u.name.toLowerCase().includes(addMemberSearchText.toLowerCase())).slice(0, 8)}
											{#if filtered.length > 0}
												<div class="absolute z-10 left-0 right-0 mt-1 bg-gray-850 border border-gray-600 rounded-lg shadow-2xl overflow-hidden max-h-56 overflow-y-auto" style="background:#1a1f2e;">
													{#each filtered as u}
														<div class="flex items-center justify-between px-4 py-2.5 hover:bg-gray-700 border-b border-gray-700/50 last:border-0 transition-colors">
															<span class="text-sm text-gray-100">{u.name}</span>
															<button
																onclick={() => addMember(g.id, u.id)}
																disabled={addMemberSaving[g.id]}
																class="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded-md disabled:opacity-30 ml-4 shrink-0"
															>추가</button>
														</div>
													{/each}
												</div>
											{:else}
												<div class="absolute z-10 left-0 right-0 mt-1 border border-gray-600 rounded-lg px-4 py-3 text-sm text-gray-500" style="background:#1a1f2e;">
													일치하는 사용자가 없습니다
												</div>
											{/if}
										{/if}
									</div>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; createError = ''; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">그룹 생성</h2>
			{#if createError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label><input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; createError = ''; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createGroup} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 수정 모달 -->
{#if editGroup}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editGroup = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editGroup = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">그룹 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label><input bind:value={editDesc} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="text-xs text-gray-500">ID: {editGroup.id}</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editGroup = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateGroup} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deleteGroup}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deleteGroup = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deleteGroup = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">그룹 삭제</h2>
			<p class="text-sm text-gray-400 mb-4"><span class="text-white font-medium">{deleteGroup.name}</span> 그룹을 삭제하시겠습니까?</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deleteGroup = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}
