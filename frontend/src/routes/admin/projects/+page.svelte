<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Project {
		id: string;
		name: string;
		description: string;
		enabled: boolean;
		domain_id: string | null;
		created_at: string | null;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}
	interface Member {
		user_id: string;
		user_name: string;
		role_id: string;
		role_name: string;
		type?: 'user' | 'group';
		group_id?: string;
	}
	interface User {
		id: string;
		name: string;
	}
	interface Group {
		id: string;
		name: string;
		description: string;
	}
	interface Role {
		id: string;
		name: string;
	}

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);

	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let form = $state({ name: '', description: '', enabled: true });

	let editProject = $state<Project | null>(null);
	let editName = $state('');
	let editDesc = $state('');
	let editEnabled = $state(true);
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deleteProject = $state<Project | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	// 접근 권한 패널
	let accessProject = $state<Project | null>(null);
	let members = $state<Member[]>([]);
	let membersLoading = $state(false);
	let allUsers = $state<User[]>([]);
	let allGroups = $state<Group[]>([]);
	let allRoles = $state<Role[]>([]);
	let addError = $state('');
	let addSaving = $state(false);
	let userSearchFilter = $state('');
	let pendingAddUser = $state<User | null>(null);
	let pendingRoleId = $state('');
	let accessTab = $state<'users' | 'groups'>('users');

	// 그룹 추가용
	let pendingAddGroup = $state<Group | null>(null);
	let pendingGroupRoleId = $state('');

	// 멤버로 이미 있는 사용자 ID 집합
	let memberUserIds = $derived(new Set(members.filter(m => m.type !== 'group').map(m => m.user_id)));
	let memberGroupIds = $derived(new Set(members.filter(m => m.type === 'group').map(m => m.group_id)));
	let filteredUsers = $derived(
		allUsers.filter(u =>
			!userSearchFilter || u.name.toLowerCase().includes(userSearchFilter.toLowerCase())
		)
	);
	let filteredGroups = $derived(
		allGroups.filter(g =>
			!userSearchFilter || g.name.toLowerCase().includes(userSearchFilter.toLowerCase())
		)
	);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(marker?: string) {
		loading = true;
		try {
			let url = `/api/admin/projects?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<Project>>(url, token, projectId);
			projects = res.items; nextMarker = res.next_marker;
		} catch { projects = []; } finally { loading = false; }
	}

	async function createProject() {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/projects', { name: form.name, description: form.description || null, enabled: form.enabled }, token, projectId);
			showCreate = false; form = { name: '', description: '', enabled: true }; await load();
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; } finally { creating = false; }
	}

	async function updateProject() {
		if (!editProject) return;
		updating = true; editError = '';
		try {
			await api.patch(`/api/admin/projects/${editProject.id}`, { name: editName, description: editDesc || null, enabled: editEnabled }, token, projectId);
			editProject = null; await load();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deleteProject) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/projects/${deleteProject.id}`, token, projectId);
			deleteProject = null; await load();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	async function openAccess(p: Project) {
		accessProject = p;
		membersLoading = true;
		addError = '';
		userSearchFilter = '';
		pendingAddUser = null;
		pendingAddGroup = null;
		pendingRoleId = '';
		pendingGroupRoleId = '';
		accessTab = 'users';
		try {
			const [m, u, r, g] = await Promise.all([
				api.get<Member[]>(`/api/admin/projects/${p.id}/members`, token, projectId),
				api.get<{ items: User[] }>('/api/admin/users?limit=100', token, projectId),
				api.get<Role[]>('/api/admin/roles', token, projectId),
				api.get<Group[]>('/api/admin/groups', token, projectId),
			]);
			members = m;
			allUsers = u.items;
			allRoles = r;
			allGroups = g;
			if (allRoles.length > 0) { pendingRoleId = allRoles[0].id; pendingGroupRoleId = allRoles[0].id; }
		} catch {
			members = [];
		} finally {
			membersLoading = false;
		}
	}

	async function assignRole(userId: string, roleId: string) {
		if (!accessProject || !userId || !roleId) return;
		addSaving = true; addError = '';
		try {
			await api.post('/api/admin/roles/assign', {
				user_id: userId,
				project_id: accessProject.id,
				role_id: roleId,
			}, token, projectId);
			pendingAddUser = null;
			await reloadMembers();
		} catch (e) { addError = e instanceof ApiError ? e.message : '할당 실패'; } finally { addSaving = false; }
	}

	async function reloadMembers() {
		if (!accessProject) return;
		try {
			members = await api.get<Member[]>(`/api/admin/projects/${accessProject.id}/members`, token, projectId);
		} catch { members = []; }
	}

	async function revokeRole(m: Member) {
		if (!accessProject) return;
		try {
			if (m.type === 'group' && m.group_id) {
				await api.delete(
					`/api/admin/roles/assign-group?group_id=${m.group_id}&project_id=${accessProject.id}&role_id=${m.role_id}`,
					token, projectId
				);
			} else {
				await api.delete(
					`/api/admin/roles/assign?user_id=${m.user_id}&project_id=${accessProject.id}&role_id=${m.role_id}`,
					token, projectId
				);
			}
			await reloadMembers();
		} catch {}
	}

	async function assignGroupRole(groupId: string, roleId: string) {
		if (!accessProject || !groupId || !roleId) return;
		addSaving = true; addError = '';
		try {
			await api.post('/api/admin/roles/assign-group', {
				group_id: groupId,
				project_id: accessProject.id,
				role_id: roleId,
			}, token, projectId);
			pendingAddGroup = null;
			await reloadMembers();
		} catch (e) { addError = e instanceof ApiError ? e.message : '그룹 할당 실패'; } finally { addSaving = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">프로젝트 관리</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<button onclick={() => load()} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}">{n}</button>
				{/each}
			</div>
		</div>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">설명</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">ID</th>
						<th class="text-left py-2 pr-4">생성일</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each projects as p (p.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors">
							<td class="py-2 pr-4 text-white">{p.name}</td>
							<td class="py-2 pr-4 text-gray-400">{p.description || '-'}</td>
							<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {p.enabled ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{p.enabled ? '활성' : '비활성'}</span></td>
							<td class="py-2 pr-4 text-gray-500 font-mono text-xs">{p.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 text-gray-500">{p.created_at?.slice(0, 10) ?? '-'}</td>
							<td class="py-2">
								<div class="flex items-center gap-1">
									<button onclick={() => { editProject = p; editName = p.name; editDesc = p.description; editEnabled = p.enabled; editError = ''; }}
										class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">수정</button>
									<button onclick={() => openAccess(p)}
										class="px-2 py-0.5 text-xs bg-blue-900/40 hover:bg-blue-800/40 text-blue-400 rounded">권한</button>
									<button onclick={() => { deleteProject = p; deleteError = ''; }}
										class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="flex items-center justify-between mt-3">
			<button disabled={markerStack.length === 0} onclick={() => { const prev = markerStack.slice(0, -1); markerStack = prev; load(prev[prev.length - 1]); }}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30">← 이전</button>
			<button disabled={!nextMarker} onclick={() => { if (nextMarker) { markerStack = [...markerStack, nextMarker]; load(nextMarker); } }}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30">다음 →</button>
		</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; createError = ''; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">프로젝트 생성</h2>
			{#if createError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label><input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="flex items-center gap-3">
					<button onclick={() => form.enabled = !form.enabled} class="relative w-11 h-6 rounded-full transition-colors {form.enabled ? 'bg-blue-600' : 'bg-gray-700'}"><span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {form.enabled ? 'translate-x-5' : ''}"></span></button>
					<span class="text-sm text-gray-300">{form.enabled ? '활성' : '비활성'}</span>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; createError = ''; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createProject} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 수정 모달 -->
{#if editProject}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editProject = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editProject = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">프로젝트 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label><input bind:value={editDesc} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="flex items-center gap-3">
					<button onclick={() => editEnabled = !editEnabled} class="relative w-11 h-6 rounded-full transition-colors {editEnabled ? 'bg-blue-600' : 'bg-gray-700'}"><span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {editEnabled ? 'translate-x-5' : ''}"></span></button>
					<span class="text-sm text-gray-300">{editEnabled ? '활성' : '비활성'}</span>
				</div>
				<div class="text-xs text-gray-500">ID: {editProject.id}</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editProject = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateProject} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deleteProject}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deleteProject = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deleteProject = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">프로젝트 삭제</h2>
			<p class="text-sm text-gray-400 mb-2"><span class="text-white font-medium">{deleteProject.name}</span> 프로젝트를 삭제하시겠습니까?</p>
			<p class="text-xs text-red-400 mb-4">이 작업은 되돌릴 수 없습니다.</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deleteProject = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 접근 권한 모달 (2패널) -->
{#if accessProject}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { accessProject = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (accessProject = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-3xl mx-4 shadow-2xl max-h-[85vh] flex flex-col" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between p-5 border-b border-gray-800">
				<div>
					<h2 class="text-lg font-semibold text-white">접근 권한 관리</h2>
					<p class="text-xs text-gray-500 mt-0.5">프로젝트: {accessProject.name}</p>
				</div>
				<button onclick={() => { accessProject = null; }} class="text-gray-400 hover:text-white text-xl">&times;</button>
			</div>

			{#if addError}
				<div class="mx-5 mt-3 bg-red-900/40 border border-red-700 text-red-300 rounded px-3 py-2 text-xs">{addError}</div>
			{/if}

			{#if membersLoading}
				<div class="text-xs text-gray-500 py-8 text-center">로딩 중...</div>
			{:else}
				<div class="flex flex-1 min-h-0">
					<!-- 왼쪽: 전체 사용자/그룹 -->
					<div class="w-1/2 border-r border-gray-800 flex flex-col">
						<div class="p-4 border-b border-gray-800">
							<!-- 사용자/그룹 탭 -->
							<div class="flex gap-1 mb-2">
								<button onclick={() => { accessTab = 'users'; userSearchFilter = ''; }}
									class="px-3 py-1 text-xs rounded {accessTab === 'users' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}">사용자</button>
								<button onclick={() => { accessTab = 'groups'; userSearchFilter = ''; }}
									class="px-3 py-1 text-xs rounded {accessTab === 'groups' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}">그룹</button>
							</div>
							<input
								type="text"
								placeholder="{accessTab === 'users' ? '사용자' : '그룹'} 이름 검색"
								bind:value={userSearchFilter}
								class="w-full bg-gray-800 border border-gray-700 text-white text-xs rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
							/>
						</div>
						<div class="overflow-y-auto flex-1">
							{#if accessTab === 'users'}
								{#each filteredUsers as u}
									<div class="flex items-center justify-between px-4 py-2 hover:bg-gray-800/50 border-b border-gray-800/30">
										<span class="text-sm text-gray-200">{u.name}</span>
										<button
											onclick={() => { pendingAddUser = u; pendingRoleId = allRoles[0]?.id ?? ''; }}
											class="text-blue-400 hover:text-blue-300 text-lg font-bold leading-none">+</button>
									</div>
								{/each}
							{:else}
								{#each filteredGroups as g}
									<div class="flex items-center justify-between px-4 py-2 hover:bg-gray-800/50 border-b border-gray-800/30">
										<div>
											<span class="text-sm text-gray-200">{g.name}</span>
											{#if memberGroupIds.has(g.id)}<span class="text-xs text-gray-600 ml-1">할당됨</span>{/if}
										</div>
										{#if !memberGroupIds.has(g.id)}
											<button
												onclick={() => { pendingAddGroup = g; pendingGroupRoleId = allRoles[0]?.id ?? ''; }}
												class="text-blue-400 hover:text-blue-300 text-lg font-bold leading-none">+</button>
										{/if}
									</div>
								{/each}
							{/if}
						</div>
					</div>

					<!-- 오른쪽: 프로젝트 멤버 -->
					<div class="w-1/2 flex flex-col">
						<div class="p-4 border-b border-gray-800">
							<div class="text-xs text-gray-400 uppercase tracking-wide">프로젝트 멤버</div>
						</div>
						<div class="overflow-y-auto flex-1">
							{#if members.length === 0}
								<div class="text-xs text-gray-600 px-4 py-4">멤버가 없습니다</div>
							{:else}
								{#each members as m}
									<div class="flex items-center justify-between px-4 py-2 hover:bg-gray-800/50 border-b border-gray-800/30">
										<div>
											<div class="text-sm text-gray-200">{m.user_name}</div>
											<div class="text-xs text-gray-500">{m.role_name}</div>
										</div>
										<button onclick={() => revokeRole(m)} class="text-red-400 hover:text-red-300 text-lg font-bold leading-none">-</button>
									</div>
								{/each}
							{/if}
						</div>
					</div>
				</div>
			{/if}

			<div class="flex justify-end p-4 border-t border-gray-800">
				<button onclick={() => { accessProject = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">닫기</button>
			</div>
		</div>
	</div>
{/if}

<!-- 사용자 역할 선택 서브 모달 -->
{#if pendingAddUser}
	<div class="fixed inset-0 bg-black/70 flex items-center justify-center z-[60]" onclick={() => { pendingAddUser = null; }} role="dialog" tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h3 class="text-base font-semibold text-white mb-3">{pendingAddUser.name} — 역할 선택</h3>
			<select bind:value={pendingRoleId} class="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500 mb-4">
				{#each allRoles as r}
					<option value={r.id}>{r.name}</option>
				{/each}
			</select>
			<div class="flex justify-end gap-3">
				<button onclick={() => { pendingAddUser = null; }} class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg">취소</button>
				<button
					onclick={() => pendingAddUser && assignRole(pendingAddUser.id, pendingRoleId)}
					disabled={addSaving || !pendingRoleId}
					class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-30"
				>{addSaving ? '추가 중...' : '추가'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 그룹 역할 선택 서브 모달 -->
{#if pendingAddGroup}
	<div class="fixed inset-0 bg-black/70 flex items-center justify-center z-[60]" onclick={() => { pendingAddGroup = null; }} role="dialog" tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h3 class="text-base font-semibold text-white mb-3">[그룹] {pendingAddGroup.name} — 역할 선택</h3>
			<select bind:value={pendingGroupRoleId} class="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500 mb-4">
				{#each allRoles as r}
					<option value={r.id}>{r.name}</option>
				{/each}
			</select>
			<div class="flex justify-end gap-3">
				<button onclick={() => { pendingAddGroup = null; }} class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg">취소</button>
				<button
					onclick={() => pendingAddGroup && assignGroupRole(pendingAddGroup.id, pendingGroupRoleId)}
					disabled={addSaving || !pendingGroupRoleId}
					class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-30"
				>{addSaving ? '추가 중...' : '추가'}</button>
			</div>
		</div>
	</div>
{/if}
