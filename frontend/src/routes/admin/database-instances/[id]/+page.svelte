<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import type { DbInstance, DbDatabase, DbUser, DbBackup } from '$lib/types/resources';
	import DbInstanceHeader from '$lib/components/admin/database-instances/id/DbInstanceHeader.svelte';
	import DbConnectionInfoCard from '$lib/components/admin/database-instances/id/DbConnectionInfoCard.svelte';
	import DbDatabasesSection from '$lib/components/admin/database-instances/id/DbDatabasesSection.svelte';
	import DbUsersSection from '$lib/components/admin/database-instances/id/DbUsersSection.svelte';
	import DbBackupsSection from '$lib/components/admin/database-instances/id/DbBackupsSection.svelte';

	const instanceId = $derived($page.params.id);
	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let instance = $state<DbInstance | null>(null);
	let databases = $state<DbDatabase[]>([]);
	let users = $state<DbUser[]>([]);
	let backups = $state<DbBackup[]>([]);
	let loading = $state(true);
	let rootInfo = $state<{ name: string; password: string } | null>(null);
	let enablingRoot = $state(false);
	let creatingDb = $state(false); let dbError = $state(''); let deletingDb = $state<string | null>(null);
	let creatingUser = $state(false); let userError = $state(''); let deletingUser = $state<string | null>(null);
	let creatingBackup = $state(false); let backupError = $state('');
	let deletingBackup = $state<string | null>(null); let restoringBackup = $state<string | null>(null);
	let deleting = $state(false);

	async function loadAll() {
		loading = true;
		await Promise.allSettled([
			api.get<DbInstance>(`/api/database-instances/${instanceId}`, token, projectId)
				.then(v => { instance = v; loading = false; })
				.catch(() => { instance = null; loading = false; }),
			api.get<DbDatabase[]>(`/api/database-instances/${instanceId}/databases`, token, projectId)
				.then(v => { databases = v; })
				.catch(() => {}),
			api.get<DbUser[]>(`/api/database-instances/${instanceId}/users`, token, projectId)
				.then(v => { users = v; })
				.catch(() => {}),
			api.get<DbBackup[]>(`/api/database-instances/${instanceId}/backups`, token, projectId)
				.then(v => { backups = v; })
				.catch(() => {}),
		]);
		loading = false;
	}

	async function deleteInstance() {
		if (!confirm(`DB 인스턴스 "${instance?.name}"를 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/database-instances/${instanceId}`, token, projectId);
			goto('/admin/database-instances');
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); deleting = false; }
	}

	async function enableRoot() {
		enablingRoot = true;
		try { rootInfo = await api.post<{ name: string; password: string }>(`/api/database-instances/${instanceId}/root`, {}, token, projectId); }
		catch (e) { alert('root 활성화 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { enablingRoot = false; }
	}

	async function createDb(form: { name: string; character_set: string; collate: string }): Promise<boolean> {
		creatingDb = true; dbError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/databases`, form, token, projectId);
			databases = await api.get<DbDatabase[]>(`/api/database-instances/${instanceId}/databases`, token, projectId);
			return true;
		} catch (e) { dbError = e instanceof ApiError ? e.message : '실패'; return false; }
		finally { creatingDb = false; }
	}

	async function deleteDb(name: string) {
		if (!confirm(`데이터베이스 "${name}"를 삭제하시겠습니까?`)) return;
		deletingDb = name;
		try {
			await api.delete(`/api/database-instances/${instanceId}/databases/${encodeURIComponent(name)}`, token, projectId);
			databases = databases.filter(d => d.name !== name);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); } finally { deletingDb = null; }
	}

	async function createUser(form: { name: string; password: string; databases: string }): Promise<boolean> {
		creatingUser = true; userError = '';
		try {
			const dbs = form.databases.split(',').map(s => s.trim()).filter(Boolean);
			await api.post(`/api/database-instances/${instanceId}/users`, { ...form, databases: dbs }, token, projectId);
			users = await api.get<DbUser[]>(`/api/database-instances/${instanceId}/users`, token, projectId);
			return true;
		} catch (e) { userError = e instanceof ApiError ? e.message : '실패'; return false; }
		finally { creatingUser = false; }
	}

	async function deleteUser(name: string) {
		if (!confirm(`유저 "${name}"를 삭제하시겠습니까?`)) return;
		deletingUser = name;
		try {
			await api.delete(`/api/database-instances/${instanceId}/users/${encodeURIComponent(name)}`, token, projectId);
			users = users.filter(u => u.name !== name);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); } finally { deletingUser = null; }
	}

	async function createBackup(form: { name: string; description: string }): Promise<boolean> {
		creatingBackup = true; backupError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/backups`, form, token, projectId);
			backups = await api.get<DbBackup[]>(`/api/database-instances/${instanceId}/backups`, token, projectId);
			return true;
		} catch (e) { backupError = e instanceof ApiError ? e.message : '실패'; return false; }
		finally { creatingBackup = false; }
	}

	async function deleteBackup(id: string) {
		if (!confirm('백업을 삭제하시겠습니까?')) return;
		deletingBackup = id;
		try {
			await api.delete(`/api/database-instances/backups/${id}`, token, projectId);
			backups = backups.filter(b => b.id !== id);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); } finally { deletingBackup = null; }
	}

	async function restoreBackup(backupId: string) {
		const name = prompt('복원할 새 인스턴스 이름:');
		if (!name) return;
		restoringBackup = backupId;
		try {
			await api.post('/api/database-instances/restore', { backup_id: backupId, name, flavor_id: instance?.flavor_id ?? '', volume_size: instance?.size ?? 5 }, token, projectId);
			alert('복원 인스턴스 생성이 시작되었습니다.');
			goto('/admin/database-instances');
		} catch (e) { alert('복원 실패: ' + (e instanceof ApiError ? e.message : String(e))); } finally { restoringBackup = null; }
	}

	onMount(loadAll);
</script>

<div class="p-4 md:p-8 max-w-4xl">
	<div class="flex items-center gap-2 mb-2">
		<a href="/admin/database-instances" class="text-gray-500 hover:text-gray-300 text-sm">DB 인스턴스</a>
		<span class="text-gray-700">/</span>
		<span class="text-white text-sm font-medium">{instance?.name ?? instanceId?.slice(0, 8)}</span>
	</div>

	{#if loading}
		<LoadingSkeleton variant="detail" rows={8} />
	{:else if !instance}
		<div class="text-gray-500 text-sm">인스턴스를 찾을 수 없습니다.</div>
	{:else}
		<DbInstanceHeader {instance} {deleting} onDelete={deleteInstance} />

		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4 grid grid-cols-2 gap-3 text-sm">
			<div><div class="text-gray-500 text-xs mb-0.5">ID</div><div class="text-gray-400 font-mono text-xs">{instance.id}</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">데이터스토어</div><div class="text-white">{instance.datastore?.type ?? '-'} {instance.datastore?.version ?? ''}</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">볼륨 크기</div><div class="text-white">{instance.size} GB</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">생성일</div><div class="text-white">{instance.created_at ? instance.created_at.slice(0, 10) : '-'}</div></div>
		</div>

		<DbConnectionInfoCard {instance} {rootInfo} {enablingRoot} onEnableRoot={enableRoot} />

		<DbDatabasesSection
			{databases}
			{deletingDb}
			addError={dbError}
			creating={creatingDb}
			onAdd={createDb}
			onDelete={deleteDb}
		/>

		<DbUsersSection
			{users}
			{deletingUser}
			addError={userError}
			creating={creatingUser}
			onAdd={createUser}
			onDelete={deleteUser}
		/>

		<DbBackupsSection
			{backups}
			{deletingBackup}
			{restoringBackup}
			addError={backupError}
			creating={creatingBackup}
			onAdd={createBackup}
			onDelete={deleteBackup}
			onRestore={restoreBackup}
		/>
	{/if}
</div>
