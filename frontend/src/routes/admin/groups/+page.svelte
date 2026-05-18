<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import type { Group, GroupMember, User } from '$lib/types/adminGroup';
	import GroupCard from '$lib/components/admin/groups/GroupCard.svelte';
	import GroupCreateModal from '$lib/components/admin/groups/GroupCreateModal.svelte';
	import GroupEditModal from '$lib/components/admin/groups/GroupEditModal.svelte';
	import GroupDeleteConfirmModal from '$lib/components/admin/groups/GroupDeleteConfirmModal.svelte';

	let groups = $state<Group[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');

	// 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');

	// 수정 모달
	let editGroup = $state<Group | null>(null);
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
	let addMemberError = $state<Record<string, string>>({});
	let addMemberSaving = $state<Record<string, boolean>>({});

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (groups.length === 0) loading = true;
		else refreshing = true;
		error = '';
		try {
			const res = await api.get<Group[]>('/api/admin/groups', token, projectId);
			groups = res;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '그룹 목록 조회 실패';
		} finally { loading = false; refreshing = false; }
	}

	async function loadUsers() {
		if (allUsers.length > 0) return;
		try {
			const res = await api.get<{ items: User[] }>('/api/admin/users?limit=100', token, projectId);
			allUsers = res.items;
		} catch {}
	}

	async function createGroup(name: string, description: string): Promise<boolean> {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/groups', { name, description: description || null }, token, projectId);
			await load();
			return true;
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; return false; }
		finally { creating = false; }
	}

	async function updateGroup(form: { name: string; description: string }): Promise<boolean> {
		if (!editGroup) return false;
		updating = true; editError = '';
		try {
			await api.patch(`/api/admin/groups/${editGroup.id}`, { name: form.name, description: form.description || null }, token, projectId);
			await load();
			return true;
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; return false; }
		finally { updating = false; }
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

	async function addMember(groupId: string, userId: string): Promise<boolean> {
		if (!userId) return false;
		addMemberSaving = { ...addMemberSaving, [groupId]: true };
		addMemberError = { ...addMemberError, [groupId]: '' };
		try {
			await api.put(`/api/admin/groups/${groupId}/users/${userId}`, {}, token, projectId);
			await loadGroupMembers(groupId);
			return true;
		} catch (e) {
			addMemberError = { ...addMemberError, [groupId]: e instanceof ApiError ? e.message : '추가 실패' };
			return false;
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

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-groups',
		defaultActive: true,
		defaultInterval: 60,
		intervalOptions: [30, 60]
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="IDENTITY / GROUPS" title="그룹">
		{#snippet actions()}
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if groups.length === 0}
		<div class="text-center text-gray-500 text-sm py-8">그룹이 없습니다</div>
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<div class="space-y-2">
				{#each groups as g (g.id)}
					<GroupCard
						group={g}
						expanded={expandedGroup === g.id}
						members={groupMembers[g.id] ?? []}
						membersLoading={membersLoading[g.id] ?? false}
						{allUsers}
						addError={addMemberError[g.id] ?? ''}
						addSaving={addMemberSaving[g.id] ?? false}
						onToggleMembers={() => toggleMembers(g)}
						onEdit={() => { editGroup = g; editError = ''; }}
						onDelete={() => { deleteGroup = g; deleteError = ''; }}
						onAddMember={(userId) => addMember(g.id, userId)}
						onRemoveMember={(userId) => removeMember(g.id, userId)}
					/>
				{/each}
			</div>
		</div>
	{/if}
</div>

<GroupCreateModal bind:open={showCreate} {creating} error={createError} onCreate={createGroup} />
<GroupEditModal bind:target={editGroup} {updating} error={editError} onSave={updateGroup} />
<GroupDeleteConfirmModal bind:target={deleteGroup} {deleting} error={deleteError} onConfirm={confirmDelete} />
