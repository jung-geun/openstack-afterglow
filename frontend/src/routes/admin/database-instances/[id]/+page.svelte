<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface DbInstance {
		id: string; name: string; status: string;
		datastore: { type?: string; version?: string };
		flavor_id: string; flavor_ram: number; size: number;
		created_at: string; hostname: string; ip: string;
	}

	interface DbDatabase { name: string; character_set: string; collate: string; }
	interface DbUser { name: string; databases: { name: string }[]; }
	interface DbBackup { id: string; name: string; status: string; size: number; created_at: string; }

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
	let showDbForm = $state(false);
	let newDb = $state({ name: '', character_set: 'utf8', collate: 'utf8_general_ci' });
	let creatingDb = $state(false); let dbError = $state(''); let deletingDb = $state<string | null>(null);
	let showUserForm = $state(false);
	let newUser = $state({ name: '', password: '', databases: '' });
	let creatingUser = $state(false); let userError = $state(''); let deletingUser = $state<string | null>(null);
	let showBackupForm = $state(false);
	let newBackup = $state({ name: '', description: '' });
	let creatingBackup = $state(false); let backupError = $state('');
	let deletingBackup = $state<string | null>(null); let restoringBackup = $state<string | null>(null);
	let deleting = $state(false);

	const statusColor: Record<string, string> = { ACTIVE: 'text-green-400', BUILD: 'text-yellow-400', ERROR: 'text-red-400', SHUTDOWN: 'text-gray-400' };
	const dsType = $derived(instance?.datastore?.type ?? '');
	const dbPort = $derived(dsType === 'postgresql' ? '5432' : dsType === 'redis' ? '6379' : dsType === 'mongodb' ? '27017' : '3306');
	const connectCmd = $derived(instance
		? dsType === 'postgresql'
			? `psql -h ${instance.ip || instance.hostname || '<host>'} -p ${dbPort} -U <user> -d <database>`
			: dsType === 'redis' ? `redis-cli -h ${instance.ip || instance.hostname || '<host>'} -p ${dbPort}`
			: `mysql -h ${instance.ip || instance.hostname || '<host>'} -P ${dbPort} -u <user> -p`
		: '');

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

	async function createDb() {
		if (!newDb.name.trim()) return;
		creatingDb = true; dbError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/databases`, newDb, token, projectId);
			showDbForm = false; newDb = { name: '', character_set: 'utf8', collate: 'utf8_general_ci' };
			databases = await api.get<DbDatabase[]>(`/api/database-instances/${instanceId}/databases`, token, projectId);
		} catch (e) { dbError = e instanceof ApiError ? e.message : '실패'; } finally { creatingDb = false; }
	}

	async function deleteDb(name: string) {
		if (!confirm(`데이터베이스 "${name}"를 삭제하시겠습니까?`)) return;
		deletingDb = name;
		try {
			await api.delete(`/api/database-instances/${instanceId}/databases/${encodeURIComponent(name)}`, token, projectId);
			databases = databases.filter(d => d.name !== name);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); } finally { deletingDb = null; }
	}

	async function createUser() {
		if (!newUser.name.trim() || !newUser.password) return;
		creatingUser = true; userError = '';
		try {
			const dbs = newUser.databases.split(',').map(s => s.trim()).filter(Boolean);
			await api.post(`/api/database-instances/${instanceId}/users`, { ...newUser, databases: dbs }, token, projectId);
			showUserForm = false; newUser = { name: '', password: '', databases: '' };
			users = await api.get<DbUser[]>(`/api/database-instances/${instanceId}/users`, token, projectId);
		} catch (e) { userError = e instanceof ApiError ? e.message : '실패'; } finally { creatingUser = false; }
	}

	async function deleteUser(name: string) {
		if (!confirm(`유저 "${name}"를 삭제하시겠습니까?`)) return;
		deletingUser = name;
		try {
			await api.delete(`/api/database-instances/${instanceId}/users/${encodeURIComponent(name)}`, token, projectId);
			users = users.filter(u => u.name !== name);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); } finally { deletingUser = null; }
	}

	async function createBackup() {
		if (!newBackup.name.trim()) return;
		creatingBackup = true; backupError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/backups`, newBackup, token, projectId);
			showBackupForm = false; newBackup = { name: '', description: '' };
			backups = await api.get<DbBackup[]>(`/api/database-instances/${instanceId}/backups`, token, projectId);
		} catch (e) { backupError = e instanceof ApiError ? e.message : '실패'; } finally { creatingBackup = false; }
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
		<div class="flex items-start justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-white">{instance.name}</h1>
				<span class="text-xs font-medium {statusColor[instance.status] ?? 'text-gray-400'}">{instance.status}</span>
			</div>
			<button onclick={deleteInstance} disabled={deleting}
				class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 transition-colors">
				{deleting ? '삭제 중...' : '인스턴스 삭제'}
			</button>
		</div>

		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4 grid grid-cols-2 gap-3 text-sm">
			<div><div class="text-gray-500 text-xs mb-0.5">ID</div><div class="text-gray-400 font-mono text-xs">{instance.id}</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">데이터스토어</div><div class="text-white">{instance.datastore?.type ?? '-'} {instance.datastore?.version ?? ''}</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">볼륨 크기</div><div class="text-white">{instance.size} GB</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">생성일</div><div class="text-white">{instance.created_at ? instance.created_at.slice(0, 10) : '-'}</div></div>
		</div>

		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
			<h2 class="text-sm font-semibold text-white mb-3">연결 정보</h2>
			<div class="space-y-2 text-sm">
				<div class="flex gap-4">
					<div><div class="text-gray-500 text-xs mb-0.5">호스트</div><div class="text-white font-mono">{instance.ip || instance.hostname || '-'}</div></div>
					<div><div class="text-gray-500 text-xs mb-0.5">포트</div><div class="text-white font-mono">{dbPort}</div></div>
				</div>
				{#if connectCmd}
					<div>
						<div class="text-gray-500 text-xs mb-1">연결 명령어 예시</div>
						<code class="block bg-gray-800 rounded px-3 py-2 text-xs text-green-400 font-mono break-all">{connectCmd}</code>
					</div>
				{/if}
				{#if rootInfo}
					<div class="bg-amber-950/30 border border-amber-800 rounded-lg px-3 py-2">
						<div class="text-amber-400 text-xs font-medium mb-1">root 계정</div>
						<div class="font-mono text-xs text-white">사용자: {rootInfo.name} / 비밀번호: {rootInfo.password}</div>
					</div>
				{:else}
					<button onclick={enableRoot} disabled={enablingRoot}
						class="text-xs text-amber-400 border border-amber-800 hover:border-amber-600 px-3 py-1.5 rounded transition-colors">
						{enablingRoot ? 'root 활성화 중...' : 'root 유저 활성화'}
					</button>
				{/if}
			</div>
		</div>

		<!-- DB 목록 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-sm font-semibold text-white">데이터베이스</h2>
				<button onclick={() => { showDbForm = !showDbForm; dbError = ''; }}
					class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
					{showDbForm ? '취소' : '+ 추가'}
				</button>
			</div>
			{#if showDbForm}
				<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
					<input type="text" bind:value={newDb.name} placeholder="database_name"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					{#if dbError}<p class="text-red-400 text-xs">{dbError}</p>{/if}
					<button onclick={createDb} disabled={creatingDb || !newDb.name.trim()}
						class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
						{creatingDb ? '생성 중...' : '생성'}
					</button>
				</div>
			{/if}
			{#if databases.length === 0}
				<div class="text-gray-600 text-xs">데이터베이스가 없습니다</div>
			{:else}
				<div class="space-y-1">
					{#each databases as db}
						<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50">
							<span class="text-white text-sm font-medium">{db.name}</span>
							<button onclick={() => deleteDb(db.name)} disabled={deletingDb === db.name}
								class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
								{deletingDb === db.name ? '...' : '삭제'}
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- 유저 목록 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-sm font-semibold text-white">유저</h2>
				<button onclick={() => { showUserForm = !showUserForm; userError = ''; }}
					class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
					{showUserForm ? '취소' : '+ 추가'}
				</button>
			</div>
			{#if showUserForm}
				<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
					<input type="text" bind:value={newUser.name} placeholder="username"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					<input type="password" bind:value={newUser.password} placeholder="비밀번호"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					<input type="text" bind:value={newUser.databases} placeholder="DB 접근 권한 (쉼표 구분)"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					{#if userError}<p class="text-red-400 text-xs">{userError}</p>{/if}
					<button onclick={createUser} disabled={creatingUser || !newUser.name.trim() || !newUser.password}
						class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
						{creatingUser ? '생성 중...' : '생성'}
					</button>
				</div>
			{/if}
			{#if users.length === 0}
				<div class="text-gray-600 text-xs">유저가 없습니다</div>
			{:else}
				<div class="space-y-1">
					{#each users as u}
						<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50">
							<div>
								<span class="text-white text-sm font-medium">{u.name}</span>
								{#if u.databases?.length}
									<span class="text-gray-500 text-xs ml-2">{u.databases.map(d => d.name).join(', ')}</span>
								{/if}
							</div>
							<button onclick={() => deleteUser(u.name)} disabled={deletingUser === u.name}
								class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
								{deletingUser === u.name ? '...' : '삭제'}
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- 백업 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-sm font-semibold text-white">백업</h2>
				<button onclick={() => { showBackupForm = !showBackupForm; backupError = ''; }}
					class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
					{showBackupForm ? '취소' : '+ 백업 생성'}
				</button>
			</div>
			{#if showBackupForm}
				<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
					<input type="text" bind:value={newBackup.name} placeholder="backup-name"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					<input type="text" bind:value={newBackup.description} placeholder="설명 (선택)"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					{#if backupError}<p class="text-red-400 text-xs">{backupError}</p>{/if}
					<button onclick={createBackup} disabled={creatingBackup || !newBackup.name.trim()}
						class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
						{creatingBackup ? '생성 중...' : '백업 생성'}
					</button>
				</div>
			{/if}
			{#if backups.length === 0}
				<div class="text-gray-600 text-xs">백업이 없습니다</div>
			{:else}
				<table class="w-full text-sm">
					<thead>
						<tr class="text-gray-500 text-xs">
							<th class="text-left py-2 font-medium">이름</th>
							<th class="text-left py-2 font-medium">상태</th>
							<th class="text-left py-2 font-medium">크기</th>
							<th class="text-left py-2 font-medium">생성일</th>
							<th class="text-right py-2 font-medium">액션</th>
						</tr>
					</thead>
					<tbody>
						{#each backups as b}
							<tr class="border-t border-gray-800/50">
								<td class="py-2 text-white">{b.name}</td>
								<td class="py-2 text-gray-400 text-xs">{b.status}</td>
								<td class="py-2 text-gray-400 text-xs">{b.size ? `${b.size} GB` : '-'}</td>
								<td class="py-2 text-gray-500 text-xs">{b.created_at ? b.created_at.slice(0, 10) : '-'}</td>
								<td class="py-2 text-right">
									<div class="flex justify-end gap-1">
										<button onclick={() => restoreBackup(b.id)} disabled={restoringBackup === b.id}
											class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-blue-900 hover:border-blue-700 transition-colors">
											{restoringBackup === b.id ? '...' : '복원'}
										</button>
										<button onclick={() => deleteBackup(b.id)} disabled={deletingBackup === b.id}
											class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
											{deletingBackup === b.id ? '...' : '삭제'}
										</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>
	{/if}
</div>
