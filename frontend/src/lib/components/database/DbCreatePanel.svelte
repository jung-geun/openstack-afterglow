<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface DbFlavor {
		id: string;
		name: string;
		ram: number;
		vcpus: number;
		disk: number;
	}
	interface Datastore {
		id: string;
		name: string;
		versions: { id: string; name: string }[];
	}
	interface Network {
		id: string;
		name: string;
		is_external: boolean;
		is_shared: boolean;
	}
	interface AZ {
		name: string;
	}
	interface VolumeType {
		id: string;
		name: string;
	}
	interface Configuration {
		id: string;
		name: string;
		datastore_name: string;
	}
	interface DbInstance {
		id: string;
		name: string;
	}
	interface DbBackup {
		id: string;
		name: string;
		instance_id: string;
	}
	interface UserDraft {
		name: string;
		password: string;
		host: string;
	}

	let {
		open = $bindable(false),
		onCreated,
	}: {
		open: boolean;
		onCreated: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// ─── 탭 정의 ─────────────────────────────────────────────────
	const TABS = ['상세 정보', '네트워킹', 'DB 접근', '초기화', '진보된'] as const;
	let activeTab = $state(0);

	// ─── 메타데이터 ───────────────────────────────────────────────
	let flavors = $state<DbFlavor[]>([]);
	let datastores = $state<Datastore[]>([]);
	let networks = $state<Network[]>([]);
	let availabilityZones = $state<AZ[]>([]);
	let volumeTypes = $state<VolumeType[]>([]);
	let configurations = $state<Configuration[]>([]);
	let instances = $state<DbInstance[]>([]);
	let backups = $state<DbBackup[]>([]);
	let loading = $state(false);
	let error = $state('');

	// ─── 폼 상태 ─────────────────────────────────────────────────
	// 탭 1: 상세 정보
	let name = $state('');
	let availabilityZone = $state('');
	let volumeSize = $state(5);
	let volumeType = $state('');
	let datastoreType = $state('');
	let datastoreVersion = $state('');
	let flavorId = $state('');
	let locality = $state('');

	// 탭 2: 네트워킹
	let selectedNics = $state<string[]>([]);

	// 탭 3: DB 접근
	let isPublic = $state(false);
	let allowedCidrs = $state('');

	// 탭 4: 초기화
	let initDatabases = $state('');
	let users = $state<UserDraft[]>([]);
	let userDraft = $state<UserDraft>({ name: '', password: '', host: '%' });

	// 탭 5: 진보된
	let configurationId = $state('');
	let restoreBackupId = $state('');
	let replicaOf = $state('');
	let replicaCount = $state(1);

	// ─── derived ─────────────────────────────────────────────────
	const selectedDs = $derived(datastores.find((d) => d.name === datastoreType));

	const step1Error = $derived.by(() => {
		if (!name.trim()) return '인스턴스 이름을 입력하세요.';
		if (!datastoreType) return '데이터스토어를 선택하세요.';
		if (!datastoreVersion) return '버전을 선택하세요.';
		if (!flavorId) return '플레이버를 선택하세요.';
		if (!volumeSize || volumeSize < 1) return '볼륨 크기를 입력하세요.';
		return '';
	});

	const canCreate = $derived(!step1Error);

	// ─── 초기화 함수 ─────────────────────────────────────────────
	function resetForm() {
		activeTab = 0;
		name = '';
		availabilityZone = '';
		volumeSize = 5;
		volumeType = '';
		locality = '';
		selectedNics = [];
		isPublic = false;
		allowedCidrs = '';
		initDatabases = '';
		users = [];
		userDraft = { name: '', password: '', host: '%' };
		configurationId = '';
		restoreBackupId = '';
		replicaOf = '';
		replicaCount = 1;
		error = '';
	}

	// ─── 패널 열기 ───────────────────────────────────────────────
	$effect(() => {
		if (!open) return;
		resetForm();
		loadMetadata();
	});

	async function loadMetadata() {
		loading = true;
		error = '';
		const opts = [token, projectId] as const;
		try {
			[flavors, datastores] = await Promise.all([
				api.get<DbFlavor[]>('/api/database-instances/flavors', ...opts),
				api.get<Datastore[]>('/api/database-instances/datastores', ...opts),
			]);
			if (flavors.length) flavorId = flavors[0].id;
			if (datastores.length) {
				datastoreType = datastores[0].name;
				datastoreVersion = datastores[0].versions[0]?.name ?? '';
			}
		} catch {
			error = '필수 메타데이터(플레이버/데이터스토어) 조회 실패';
		}
		// fail-soft 목록들
		await Promise.allSettled([
			api
				.get<Network[]>('/api/networks', ...opts)
				.then((v) => (networks = v.filter(n => !n.is_external && !n.is_shared)))
				.catch(() => {}),
			api
				.get<AZ[]>('/api/instances/availability-zones', ...opts)
				.then((v) => (availabilityZones = v))
				.catch(() => {}),
			api
				.get<VolumeType[]>('/api/database-instances/volume-types', ...opts)
				.then((v) => (volumeTypes = v))
				.catch(() => {}),
			api
				.get<Configuration[]>('/api/database-instances/configurations', ...opts)
				.then((v) => (configurations = v))
				.catch(() => {}),
			api
				.get<DbInstance[]>('/api/database-instances', ...opts)
				.then((v) => (instances = v))
				.catch(() => {}),
			api
				.get<DbBackup[]>('/api/database-instances/backups', ...opts)
				.then((v) => (backups = v))
				.catch(() => {}),
		]);
		loading = false;
	}

	// ─── NIC 토글 ────────────────────────────────────────────────
	function toggleNic(id: string) {
		if (selectedNics.includes(id)) {
			selectedNics = selectedNics.filter((n) => n !== id);
		} else {
			selectedNics = [...selectedNics, id];
		}
	}

	// ─── 유저 추가 ───────────────────────────────────────────────
	function addUser() {
		if (!userDraft.name.trim() || !userDraft.password) return;
		users = [...users, { ...userDraft }];
		userDraft = { name: '', password: '', host: '%' };
	}

	function removeUser(i: number) {
		users = users.filter((_, idx) => idx !== i);
	}

	// ─── 생성 ────────────────────────────────────────────────────
	let creating = $state(false);
	let createError = $state('');

	async function createInstance() {
		if (!canCreate) return;
		creating = true;
		createError = '';
		const dbs = initDatabases
			.split(',')
			.map((s) => s.trim())
			.filter(Boolean);
		const cidrs = allowedCidrs
			.split(',')
			.map((s) => s.trim())
			.filter(Boolean);
		const body = {
			name: name.trim(),
			flavor_id: flavorId,
			volume_size: volumeSize,
			datastore_type: datastoreType,
			datastore_version: datastoreVersion,
			availability_zone: availabilityZone || null,
			volume_type: volumeType || null,
			nics: selectedNics,
			locality: replicaOf ? (locality || null) : null,
			databases: dbs,
			users: users.map((u) => ({ name: u.name, password: u.password, host: u.host })),
			is_public: isPublic,
			allowed_cidrs: cidrs,
			configuration_id: configurationId || null,
			restore_backup_id: restoreBackupId || null,
			replica_of: replicaOf || null,
			replica_count: replicaOf && replicaCount > 1 ? replicaCount : null,
		};
		try {
			await api.post('/api/database-instances', body, token, projectId);
			open = false;
			onCreated();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : 'DB 인스턴스 생성 실패';
		} finally {
			creating = false;
		}
	}

	// ─── 입력 스타일 공통 ────────────────────────────────────────
	const inputCls =
		'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500';
	const labelCls = 'block text-xs text-gray-400 mb-1';
</script>

{#if open}
	<!-- 오버레이 -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => (open = false)}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl mx-4 shadow-2xl flex flex-col max-h-[90vh]"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
		>
			<!-- 헤더 -->
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-800">
				<h2 class="text-base font-semibold text-white">DB 인스턴스 생성</h2>
				<button
					onclick={() => (open = false)}
					class="text-gray-400 hover:text-white text-xl leading-none">&times;</button
				>
			</div>

			<!-- 탭 네비게이션 -->
			<div class="flex border-b border-gray-800 px-6 gap-0 overflow-x-auto">
				{#each TABS as tab, i}
					<button
						onclick={() => (activeTab = i)}
						class="text-xs py-3 px-4 border-b-2 whitespace-nowrap transition-colors
							{activeTab === i
							? 'border-amber-500 text-amber-400 font-medium'
							: 'border-transparent text-gray-500 hover:text-gray-300'}"
					>
						{tab}
						{#if i === 0 && step1Error && name}
							<span class="ml-1 text-red-400">*</span>
						{/if}
					</button>
				{/each}
			</div>

			<!-- 탭 콘텐츠 -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				{#if loading}
					<p class="text-gray-400 text-sm">메타데이터 불러오는 중...</p>
				{:else if error}
					<div class="bg-red-900/20 border border-red-800 rounded-lg px-3 py-2 text-red-400 text-xs">
						{error}
					</div>
				{:else if activeTab === 0}
					<!-- ── 탭 1: 상세 정보 ── -->
					<div class="space-y-4">
						<div>
							<label class={labelCls}>인스턴스 이름 <span class="text-red-400">*</span></label>
							<input type="text" bind:value={name} placeholder="my-database" class={inputCls} />
						</div>

						<div class="grid grid-cols-2 gap-3">
							<div>
								<label class={labelCls}>데이터스토어 <span class="text-red-400">*</span></label>
								{#if datastores.length}
									<select
										bind:value={datastoreType}
										onchange={() => {
											const ds = datastores.find((d) => d.name === datastoreType);
											datastoreVersion = ds?.versions[0]?.name ?? '';
										}}
										class={inputCls}
									>
										{#each datastores as ds}
											<option value={ds.name}>{ds.name}</option>
										{/each}
									</select>
								{:else}
									<input type="text" bind:value={datastoreType} placeholder="mysql" class={inputCls} />
								{/if}
							</div>
							<div>
								<label class={labelCls}>버전 <span class="text-red-400">*</span></label>
								{#if selectedDs?.versions.length}
									<select bind:value={datastoreVersion} class={inputCls}>
										{#each selectedDs.versions as v}
											<option value={v.name}>{v.name}</option>
										{/each}
									</select>
								{:else}
									<input type="text" bind:value={datastoreVersion} placeholder="5.7" class={inputCls} />
								{/if}
							</div>
						</div>

						<div>
							<label class={labelCls}>플레이버 <span class="text-red-400">*</span></label>
							{#if flavors.length}
								<select bind:value={flavorId} class={inputCls}>
									{#each flavors as f}
										<option value={f.id}>{f.name} ({f.vcpus} vCPU · {Math.round(f.ram / 1024)} GB RAM)</option>
									{/each}
								</select>
							{:else}
								<input type="text" bind:value={flavorId} placeholder="flavor ID" class={inputCls} />
							{/if}
						</div>

						<div class="grid grid-cols-2 gap-3">
							<div>
								<label class={labelCls}>볼륨 크기 (GB) <span class="text-red-400">*</span></label>
								<input
									type="number"
									bind:value={volumeSize}
									min="1"
									max="1024"
									class={inputCls}
								/>
							</div>
							<div>
								<label class={labelCls}>볼륨 타입</label>
								<select bind:value={volumeType} class={inputCls}>
									<option value="">기본값</option>
									{#each volumeTypes as vt}
										<option value={vt.name}>{vt.name}</option>
									{/each}
								</select>
								<p class="text-xs text-gray-500 mt-1">기본값을 권장합니다. 모든 Cinder 타입이 Trove 와 호환되지 않습니다.</p>
							</div>
						</div>

						<div>
							<label class={labelCls}>가용 구역</label>
							<select bind:value={availabilityZone} class={inputCls}>
								<option value="">자동 선택</option>
								{#each availabilityZones as az}
									<option value={az.name}>{az.name}</option>
								{/each}
							</select>
						</div>
					</div>
				{:else if activeTab === 1}
					<!-- ── 탭 2: 네트워킹 ── -->
					<div class="space-y-3">
						<p class="text-xs text-gray-400">
							사용할 네트워크를 선택하세요. 선택하지 않으면 Trove가 기본 네트워크를 사용합니다.
						</p>
						{#if networks.length === 0}
							<p class="text-gray-500 text-sm">사용 가능한 네트워크가 없습니다.</p>
						{:else}
							<div class="space-y-2">
								{#each networks as net}
									<label
										class="flex items-center gap-3 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 cursor-pointer hover:border-amber-500/50 transition-colors"
									>
										<input
											type="checkbox"
											checked={selectedNics.includes(net.id)}
											onchange={() => toggleNic(net.id)}
											class="accent-amber-500"
										/>
										<span class="text-sm text-white">{net.name}</span>
										<span class="text-xs text-gray-500 font-mono">{net.id.slice(0, 8)}…</span>
									</label>
								{/each}
							</div>
						{/if}
					</div>
				{:else if activeTab === 2}
					<!-- ── 탭 3: DB 접근 ── -->
					<div class="space-y-4">
						<label class="flex items-center gap-3 cursor-pointer">
							<input type="checkbox" bind:checked={isPublic} class="accent-amber-500" />
							<span class="text-sm text-white">Is Public</span>
						</label>
						<p class="text-xs text-gray-400">
							퍼블릭으로 설정하면 모든 IP에서 접근 가능합니다. 제한이 필요하면 아래 CIDR을 설정하세요.
						</p>
						<div>
							<label class={labelCls}>Allowed CIDRs (쉼표 구분, 비어있으면 0.0.0.0/0)</label>
							<input
								type="text"
								bind:value={allowedCidrs}
								placeholder="10.0.0.0/24, 192.168.1.0/24"
								class={inputCls}
							/>
						</div>
					</div>
				{:else if activeTab === 3}
					<!-- ── 탭 4: 초기화 ── -->
					<div class="space-y-4">
						<div>
							<label class={labelCls}>초기 데이터베이스 (쉼표 구분)</label>
							<input
								type="text"
								bind:value={initDatabases}
								placeholder="mydb, testdb"
								class={inputCls}
							/>
							<p class="text-xs text-gray-500 mt-1">생성 시 자동으로 만들어질 데이터베이스 목록</p>
						</div>
						<div class="border border-gray-700 rounded-lg p-4">
							<h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">초기 관리자</h4>
							<div class="grid grid-cols-3 gap-2 mb-2">
								<div>
									<label class={labelCls}>사용자명</label>
									<input type="text" bind:value={userDraft.name} placeholder="admin" class={inputCls} />
								</div>
								<div>
									<label class={labelCls}>암호</label>
									<input
										type="password"
										bind:value={userDraft.password}
										placeholder="••••••••"
										class={inputCls}
									/>
								</div>
								<div>
									<label class={labelCls}>허용 호스트</label>
									<input type="text" bind:value={userDraft.host} placeholder="%" class={inputCls} />
								</div>
							</div>
							<button
								onclick={addUser}
								disabled={!userDraft.name.trim() || !userDraft.password}
								class="text-xs text-amber-400 hover:text-amber-300 disabled:text-gray-600"
							>
								+ 추가
							</button>
							{#if users.length}
								<div class="mt-3 space-y-1">
									{#each users as u, i}
										<div
											class="flex items-center justify-between bg-gray-800 rounded px-3 py-1.5 text-xs"
										>
											<span class="text-white font-mono">{u.name}@{u.host}</span>
											<button
												onclick={() => removeUser(i)}
												class="text-red-400 hover:text-red-300">제거</button
											>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{:else}
					<!-- ── 탭 5: 진보된 ── -->
					<div class="space-y-4">
						<div>
							<label class={labelCls}>Configuration group</label>
							<select bind:value={configurationId} class={inputCls}>
								<option value="">없음</option>
								{#each configurations as cfg}
									<option value={cfg.id}>{cfg.name} ({cfg.datastore_name})</option>
								{/each}
							</select>
						</div>
						<div>
							<label class={labelCls}>백업에서 복원 (초기 상태 원본)</label>
							<select bind:value={restoreBackupId} class={inputCls}>
								<option value="">새 인스턴스</option>
								{#each backups as b}
									<option value={b.id}>{b.name}</option>
								{/each}
							</select>
						</div>
						<div>
							<label class={labelCls}>복제 원본 인스턴스</label>
							<select bind:value={replicaOf} class={inputCls}>
								<option value="">없음</option>
								{#each instances as inst}
									<option value={inst.id}>{inst.name}</option>
								{/each}
							</select>
						</div>
						{#if replicaOf}
							<div>
								<label class={labelCls}>복제 개수</label>
								<input type="number" bind:value={replicaCount} min="1" max="10" class={inputCls} />
							</div>
						{/if}
						<div>
							<label class={labelCls}>배치 정책 (Locality)</label>
							<select bind:value={locality} disabled={!replicaOf} class={inputCls}>
								<option value="">없음</option>
								<option value="affinity">Affinity</option>
								<option value="anti-affinity">Anti-Affinity</option>
							</select>
							{#if !replicaOf}
								<p class="text-xs text-gray-500 mt-1">복제 인스턴스 생성 시에만 적용됩니다.</p>
							{/if}
						</div>
					</div>
				{/if}
			</div>

			<!-- 에러 + 액션 -->
			<div class="px-6 py-4 border-t border-gray-800 space-y-3">
				{#if createError}
					<div class="bg-red-900/20 border border-red-800 rounded-lg px-3 py-2 text-red-400 text-xs whitespace-pre-wrap break-all">
						{createError}
					</div>
				{:else if step1Error && activeTab !== 0}
					<div class="text-amber-400 text-xs">{step1Error}</div>
				{/if}
				<div class="flex items-center justify-between">
					<div class="flex gap-2">
						{#if activeTab > 0}
							<button
								onclick={() => (activeTab -= 1)}
								class="text-xs text-gray-400 hover:text-white px-3 py-1.5 border border-gray-700 rounded-lg"
							>
								← 이전
							</button>
						{/if}
						{#if activeTab < TABS.length - 1}
							<button
								onclick={() => (activeTab += 1)}
								class="text-xs text-amber-400 hover:text-amber-300 px-3 py-1.5 border border-amber-700 rounded-lg"
							>
								다음 →
							</button>
						{/if}
					</div>
					<div class="flex gap-2">
						<button
							onclick={() => (open = false)}
							class="text-xs text-gray-400 hover:text-white px-4 py-1.5 border border-gray-700 rounded-lg"
						>
							취소
						</button>
						<button
							onclick={createInstance}
							disabled={creating || !canCreate}
							title={step1Error || ''}
							class="text-xs text-white bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 px-4 py-1.5 rounded-lg transition-colors"
						>
							{creating ? '생성 중...' : '생성'}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
