<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import type { FloatingIp } from '$lib/types/resources';

	interface DbInstance {
		id: string;
		name: string;
		status: string;
		datastore: { type?: string; version?: string };
		flavor_id: string;
		flavor_ram: number;
		flavor_vcpus: number;
		size: number;
		volume_used: number;
		created_at: string;
		updated_at: string;
		hostname: string;
		ip: string;
		ips: string[];
		address_map?: Record<string, string[]>;
	}

	interface DbFlavor { id: string; name: string; ram: number; vcpus: number; disk: number; }
	interface DbDatabase { name: string; character_set: string; collate: string; }
	interface DbUser { name: string; host: string; databases: { name: string }[]; }
	interface DbBackup {
		id: string; name: string; status: string;
		size: number; created_at: string; description: string;
	}
	interface Props {
		instanceId: string;
		token?: string;
		projectId?: string;
		onClose?: () => void;
		onDeleted?: () => void;
	}

	let { instanceId, token, projectId, onClose, onDeleted }: Props = $props();

	let instance = $state<DbInstance | null>(null);
	let databases = $state<DbDatabase[]>([]);
	let users = $state<DbUser[]>([]);
	let backups = $state<DbBackup[]>([]);
	let flavors = $state<DbFlavor[]>([]);
	let loading = $state(true);

	let rootInfo = $state<{ name: string; password: string } | null>(null);
	let enablingRoot = $state(false);

	let showDbForm = $state(false);
	let newDb = $state({ name: '', character_set: 'utf8', collate: 'utf8_general_ci' });
	let creatingDb = $state(false);
	let dbError = $state('');
	let deletingDb = $state<string | null>(null);

	let showUserForm = $state(false);
	let newUser = $state<{ name: string; password: string; host: string; dbNames: string[] }>({
		name: '', password: '', host: '%', dbNames: []
	});
	let creatingUser = $state(false);
	let userError = $state('');
	let deletingUser = $state<string | null>(null);

	let showBackupForm = $state(false);
	let newBackup = $state({ name: '', description: '' });
	let creatingBackup = $state(false);
	let backupError = $state('');
	let deletingBackup = $state<string | null>(null);
	let restoringBackup = $state<string | null>(null);

	let deleting = $state(false);

	let floatingIps = $state<FloatingIp[]>([]);
	let attachingFip = $state(false);
	let detachingFip = $state(false);
	let fipError = $state('');

	const instanceFips = $derived.by(() => {
		const ips = instance?.ips ?? [];
		return floatingIps.filter(f => f.fixed_ip_address && ips.includes(f.fixed_ip_address));
	});

	const statusColor: Record<string, string> = {
		ACTIVE: 'text-green-400',
		BUILD: 'text-yellow-400',
		ERROR: 'text-red-400',
		SHUTDOWN: 'text-gray-400',
	};

	const statusLabel: Record<string, string> = {
		SHUTDOWN: '삭제 중',
	};

	const dsType = $derived(instance?.datastore?.type ?? '');
	const flavorDisplay = $derived.by(() => {
		const inst = instance;
		if (!inst?.flavor_id) return '-';
		const f = flavors.find(x => String(x.id) === String(inst.flavor_id));
		if (f) return `${f.name} (${f.vcpus}vCPU / ${f.ram}MB)`;
		const ramVcpu = inst.flavor_vcpus || inst.flavor_ram
			? ` (${inst.flavor_vcpus}vCPU / ${inst.flavor_ram}MB)` : '';
		return `${inst.flavor_id}${ramVcpu}`;
	});
	const dbPort = $derived(
		dsType === 'postgresql' ? '5432' :
		dsType === 'redis' ? '6379' :
		dsType === 'mongodb' ? '27017' : '3306'
	);
	const connectHost = $derived(
		instance ? (instance.ips?.[0] || instance.hostname || '<host>') : '<host>'
	);
	const connectCmd = $derived(
		instance
			? dsType === 'postgresql'
				? `psql -h ${connectHost} -p ${dbPort} -U <user> -d <database>`
				: dsType === 'redis'
				? `redis-cli -h ${connectHost} -p ${dbPort}`
				: `mysql -h ${connectHost} -P ${dbPort} -u <user> -p`
			: ''
	);

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
			flavors.length === 0
				? api.get<DbFlavor[]>('/api/database-instances/flavors', token, projectId)
					.then(v => { flavors = v; })
					.catch(() => {})
				: Promise.resolve(),
			api.get<FloatingIp[]>('/api/networks/floating-ips', token, projectId)
				.then(v => { floatingIps = v; })
				.catch(() => {}),
		]);
		loading = false;
	}

	async function attachFip() {
		attachingFip = true; fipError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/floating-ip`, {}, token, projectId);
			floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', token, projectId);
		} catch (e) { fipError = e instanceof ApiError ? e.message : '실패'; }
		finally { attachingFip = false; }
	}

	async function detachFip(deleteFip: boolean) {
		const verb = deleteFip ? '삭제' : '해제';
		if (!confirm(`이 인스턴스의 floating IP를 ${verb}하시겠습니까?`)) return;
		detachingFip = true; fipError = '';
		try {
			await api.delete(
				`/api/database-instances/${instanceId}/floating-ip${deleteFip ? '?delete=true' : ''}`,
				token, projectId
			);
			floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', token, projectId);
		} catch (e) { fipError = e instanceof ApiError ? e.message : '실패'; }
		finally { detachingFip = false; }
	}

	async function deleteInstance() {
		if (!confirm(`DB 인스턴스 "${instance?.name}"를 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/database-instances/${instanceId}`, token, projectId);
			onDeleted?.();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			deleting = false;
		}
	}

	async function enableRoot() {
		enablingRoot = true;
		try {
			rootInfo = await api.post<{ name: string; password: string }>(
				`/api/database-instances/${instanceId}/root`, {}, token, projectId
			);
		} catch (e) {
			alert('root 활성화 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			enablingRoot = false;
		}
	}

	async function createDb() {
		if (!newDb.name.trim()) return;
		creatingDb = true; dbError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/databases`, newDb, token, projectId);
			showDbForm = false; newDb = { name: '', character_set: 'utf8', collate: 'utf8_general_ci' };
			databases = await api.get<DbDatabase[]>(`/api/database-instances/${instanceId}/databases`, token, projectId);
		} catch (e) { dbError = e instanceof ApiError ? e.message : '실패'; }
		finally { creatingDb = false; }
	}

	async function deleteDb(name: string) {
		if (!confirm(`데이터베이스 "${name}"를 삭제하시겠습니까?`)) return;
		deletingDb = name;
		try {
			await api.delete(`/api/database-instances/${instanceId}/databases/${encodeURIComponent(name)}`, token, projectId);
			databases = databases.filter(d => d.name !== name);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { deletingDb = null; }
	}

	async function createUser() {
		if (!newUser.name.trim() || !newUser.password) return;
		creatingUser = true; userError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/users`, {
				name: newUser.name,
				password: newUser.password,
				host: newUser.host || '%',
				databases: newUser.dbNames,
			}, token, projectId);
			showUserForm = false; newUser = { name: '', password: '', host: '%', dbNames: [] };
			users = await api.get<DbUser[]>(`/api/database-instances/${instanceId}/users`, token, projectId);
		} catch (e) { userError = e instanceof ApiError ? e.message : '실패'; }
		finally { creatingUser = false; }
	}

	async function deleteUser(u: DbUser) {
		const host = u.host || '%';
		const label = host !== '%' ? `${u.name}@${host}` : u.name;
		if (!confirm(`유저 "${label}"를 삭제하시겠습니까?`)) return;
		deletingUser = label;
		try {
			const url = `/api/database-instances/${instanceId}/users/${encodeURIComponent(u.name)}`
				+ `?host=${encodeURIComponent(host)}`;
			await api.delete(url, token, projectId);
			users = users.filter(x => !(x.name === u.name && x.host === u.host));
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { deletingUser = null; }
	}

	async function createBackup() {
		if (!newBackup.name.trim()) return;
		creatingBackup = true; backupError = '';
		try {
			await api.post(`/api/database-instances/${instanceId}/backups`, newBackup, token, projectId);
			showBackupForm = false; newBackup = { name: '', description: '' };
			backups = await api.get<DbBackup[]>(`/api/database-instances/${instanceId}/backups`, token, projectId);
		} catch (e) { backupError = e instanceof ApiError ? e.message : '실패'; }
		finally { creatingBackup = false; }
	}

	async function deleteBackup(id: string) {
		if (!confirm('백업을 삭제하시겠습니까?')) return;
		deletingBackup = id;
		try {
			await api.delete(`/api/database-instances/backups/${id}`, token, projectId);
			backups = backups.filter(b => b.id !== id);
		} catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { deletingBackup = null; }
	}

	async function restoreBackup(backupId: string) {
		const name = prompt('복원할 새 인스턴스 이름을 입력하세요:');
		if (!name) return;
		restoringBackup = backupId;
		try {
			await api.post('/api/database-instances/restore', {
				backup_id: backupId, name,
				flavor_id: instance?.flavor_id ?? '',
				volume_size: instance?.size ?? 5,
			}, token, projectId);
			alert('복원 인스턴스 생성이 시작되었습니다.');
			onDeleted?.();
		} catch (e) { alert('복원 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { restoringBackup = null; }
	}

	const ar = createAutoRefresh(() => loadAll(), {
		storageKey: 'dashboard-db-instance-detail',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		if (instanceId) {
			instance = null;
			databases = [];
			users = [];
			backups = [];
			rootInfo = null;
			loading = true;
			loadAll();
		}
	});
</script>

<div class="p-4 md:p-6 space-y-4">
	<!-- 헤더 -->
	<div class="flex items-start justify-between">
		<div>
			{#if loading && !instance}
				<div class="h-7 w-40 bg-gray-800 rounded animate-pulse mb-1"></div>
			{:else}
				<h1 class="text-xl font-bold text-white">{instance?.name ?? instanceId.slice(0, 8)}</h1>
				<span class="text-xs font-medium {statusColor[instance?.status ?? ''] ?? 'text-gray-400'}">
					{statusLabel[instance?.status ?? ''] ?? instance?.status ?? ''}
				</span>
			{/if}
		</div>
		<div class="flex items-center gap-2 flex-shrink-0">
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={() => loadAll()}
			/>
			{#if instance}
				<button onclick={deleteInstance} disabled={deleting}
					class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-red-900 hover:border-red-700 transition-colors">
					{deleting ? '삭제 중...' : '인스턴스 삭제'}
				</button>
			{/if}
			{#if onClose}
				<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none ml-1">×</button>
			{/if}
		</div>
	</div>

	{#if loading && !instance}
		<LoadingSkeleton variant="detail" rows={8} />
	{:else if !instance}
		<div class="text-gray-500 text-sm">인스턴스를 찾을 수 없습니다.</div>
	{:else}
		<!-- 인스턴스 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 grid grid-cols-1 @3xl/panel:grid-cols-2 gap-3 text-sm">
			<div class="col-span-2"><div class="text-gray-500 text-xs mb-0.5">ID</div><div class="text-gray-400 font-mono text-xs break-all">{instance.id}</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">데이터스토어</div><div class="text-white">{instance.datastore?.type ?? '-'} {instance.datastore?.version ?? ''}</div></div>
			<div><div class="text-gray-500 text-xs mb-0.5">생성일</div><div class="text-white">{instance.created_at ? instance.created_at.slice(0, 10) : '-'}</div></div>
			<div>
				<div class="text-gray-500 text-xs mb-0.5">볼륨 크기</div>
				<div class="text-white">
					{instance.size} GB
					{#if instance.volume_used > 0}
						<span class="text-gray-500 text-xs ml-1">({instance.volume_used} GB 사용)</span>
					{/if}
				</div>
			</div>
			<div>
				<div class="text-gray-500 text-xs mb-0.5">플레이버</div>
				<div class="text-white text-xs">{flavorDisplay}</div>
			</div>
			{#if instance.address_map && Object.keys(instance.address_map).length > 0}
				<div class="col-span-2">
					<div class="text-gray-500 text-xs mb-1">IP 주소</div>
					<div class="space-y-1">
						{#each Object.entries(instance.address_map) as [netName, addrs]}
							<div class="flex flex-wrap items-center gap-2">
								<span class="text-gray-400 text-xs">{netName}:</span>
								{#each addrs as addr}
									<span class="text-white font-mono text-xs bg-gray-800 px-2 py-0.5 rounded">{addr}</span>
								{/each}
							</div>
						{/each}
					</div>
				</div>
			{:else if instance.ips?.length > 0}
				<div class="col-span-2">
					<div class="text-gray-500 text-xs mb-1">IP 주소</div>
					<div class="flex flex-wrap gap-1.5">
						{#each instance.ips as addr}
							<span class="text-white font-mono text-xs bg-gray-800 px-2 py-0.5 rounded">{addr}</span>
						{/each}
					</div>
				</div>
			{/if}
			{#if instance.hostname}
				<div class="col-span-2"><div class="text-gray-500 text-xs mb-0.5">호스트명</div><div class="text-white font-mono text-xs">{instance.hostname}</div></div>
			{/if}
		</div>

		<!-- 연결 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
			<h2 class="text-sm font-semibold text-white mb-3">연결 정보</h2>
			<div class="space-y-2 text-sm">
				<div class="flex gap-4">
					<div class="flex-1">
						<div class="text-gray-500 text-xs mb-0.5">호스트</div>
						{#if instance.address_map && Object.keys(instance.address_map).length > 0}
							<div class="space-y-0.5">
								{#each Object.entries(instance.address_map) as [netName, addrs]}
									{#each addrs as addr}
										<div class="text-white font-mono text-sm">
											<span class="text-gray-400 text-xs mr-1.5">{netName}:</span>{addr}
										</div>
									{/each}
								{/each}
							</div>
						{:else if instance.ips?.length > 0}
							<div class="space-y-0.5">
								{#each instance.ips as addr}
									<div class="text-white font-mono text-sm">{addr}</div>
								{/each}
							</div>
						{:else}
							<div class="text-gray-500 font-mono">-</div>
						{/if}
					</div>
					<div><div class="text-gray-500 text-xs mb-0.5">포트</div><div class="text-white font-mono">{dbPort}</div></div>
				</div>
				<!-- 공개 IP (Floating IP) -->
				<div>
					<div class="text-gray-500 text-xs mb-1">공개 IP (Floating)</div>
					{#if instanceFips.length > 0}
						<div class="flex flex-wrap items-center gap-2">
							{#each instanceFips as fip}
								<span class="text-emerald-400 font-mono text-sm bg-emerald-950/40 border border-emerald-800/50 px-2 py-0.5 rounded">{fip.floating_ip_address}</span>
							{/each}
							<button onclick={() => detachFip(false)} disabled={detachingFip}
								class="text-gray-400 hover:text-gray-200 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-gray-700 hover:border-gray-500 transition-colors">
								{detachingFip ? '...' : '해제'}
							</button>
							<button onclick={() => detachFip(true)} disabled={detachingFip}
								class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
								{detachingFip ? '...' : '삭제'}
							</button>
						</div>
					{:else if instance?.status === 'BUILD' || instance?.status === 'BUILDING'}
						<div class="flex items-center gap-2 text-sm text-yellow-400">
							<svg class="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
							<span class="text-xs">인스턴스 생성 중... Floating IP는 완료 후 자동 할당됩니다.</span>
						</div>
					{:else}
						<div class="flex items-center gap-2">
							<span class="text-gray-500 text-sm">미할당</span>
							<button onclick={attachFip} disabled={attachingFip || !instance.ip}
								class="text-amber-400 hover:text-amber-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-amber-900 hover:border-amber-700 transition-colors">
								{attachingFip ? '할당 중...' : '+ 공개 IP 할당'}
							</button>
						</div>
					{/if}
					{#if fipError}<p class="text-red-400 text-xs mt-1">{fipError}</p>{/if}
				</div>
				{#if connectCmd}
					<div>
						<div class="text-gray-500 text-xs mb-1">연결 명령어 예시</div>
						<code class="block bg-gray-800 rounded px-3 py-2 text-xs text-green-400 font-mono break-all">{connectCmd}</code>
					</div>
				{/if}
				{#if rootInfo}
					<div class="bg-amber-950/30 border border-amber-800 rounded-lg px-3 py-2">
						<div class="text-amber-400 text-xs font-medium mb-1">root 계정 활성화됨</div>
						<div class="font-mono text-xs text-white">사용자: {rootInfo.name}</div>
						<div class="font-mono text-xs text-white">비밀번호: {rootInfo.password}</div>
					</div>
				{:else}
					<button onclick={enableRoot} disabled={enablingRoot}
						class="text-xs text-amber-400 border border-amber-800 hover:border-amber-600 px-3 py-1.5 rounded transition-colors">
						{enablingRoot ? 'root 활성화 중...' : 'root 유저 활성화'}
					</button>
				{/if}
			</div>
		</div>

		<!-- 데이터베이스 목록 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
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
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
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
					<input type="text" bind:value={newUser.host} placeholder="host (예: %, localhost, 10.0.0.%)"
						class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
					{#if databases.length > 0}
						<div>
							<div class="text-gray-400 text-xs mb-1.5">DB 접근 권한 (선택)</div>
							<div class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
								{#each databases as db}
									<label class="flex items-center gap-1.5 text-xs text-white bg-gray-700 hover:bg-gray-600 border border-gray-600 px-2 py-1 rounded cursor-pointer">
										<input type="checkbox" bind:group={newUser.dbNames} value={db.name} class="accent-amber-500" />
										{db.name}
									</label>
								{/each}
							</div>
						</div>
					{:else}
						<div class="text-gray-600 text-xs">먼저 데이터베이스를 생성하면 권한을 부여할 수 있습니다</div>
					{/if}
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
					{#each users as u (u.name + '@' + u.host)}
						{@const userKey = u.host && u.host !== '%' ? `${u.name}@${u.host}` : u.name}
						<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50">
							<div>
								<span class="text-white text-sm font-medium font-mono">
									{u.name}<span class="text-gray-500">@{u.host || '%'}</span>
								</span>
								{#if u.databases?.length}
									<span class="text-gray-500 text-xs ml-2">{u.databases.map(d => d.name).join(', ')}</span>
								{/if}
							</div>
							<button onclick={() => deleteUser(u)} disabled={deletingUser === userKey}
								class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
								{deletingUser === userKey ? '...' : '삭제'}
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
