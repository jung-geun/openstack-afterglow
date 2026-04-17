<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { goto } from '$app/navigation';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface IpAddress {
		addr: string;
		type: string;
		network_name: string;
	}

	interface Instance {
		id: string;
		name: string;
		status: string;
		image_id: string | null;
		image_name: string | null;
		flavor_id: string | null;
		flavor_name: string | null;
		ip_addresses: IpAddress[];
		created_at: string | null;
		metadata: Record<string, string>;
		union_libraries: string[];
		union_strategy: string | null;
		union_share_ids: string[];
		union_upper_volume_id: string | null;
		key_name: string | null;
		user_id: string | null;
	}

	interface FloatingIp {
		id: string;
		floating_ip_address: string;
		fixed_ip_address: string | null;
		status: string;
		port_id: string | null;
		floating_network_id: string;
	}

	interface PortInfo {
		id: string;
		network_id: string;
		mac_address: string;
		fixed_ips: { ip_address: string; subnet_id: string }[];
		security_group_ids: string[];
		status: string;
	}

	interface VolumeAttachment {
		id: string;
		volume_id: string;
		device: string;
		name?: string;
		size?: number;
		status?: string;
	}

	interface SecurityGroup {
		id: string;
		name: string;
		description: string;
		rules: any[];
	}

	interface VolumeInfo {
		id: string;
		name: string;
		status: string;
		size: number;
		attachments: any[];
	}

	interface NetworkInfo {
		id: string;
		name: string;
		status: string;
		is_external: boolean;
		is_shared: boolean;
	}

	interface Props {
		instanceId: string;
		onClose?: () => void;
		adminProjectId?: string | null;  // 관리자가 다른 프로젝트의 인스턴스를 볼 때
	}

	let { instanceId, onClose, adminProjectId = null }: Props = $props();

	let instance = $state<Instance | null>(null);
	const fixedIpsList = $derived(instance?.ip_addresses.filter(ip => ip.type === 'fixed') ?? []);
	const floatingIpsList = $derived(instance?.ip_addresses.filter(ip => ip.type === 'floating') ?? []);
	let floatingIps = $state<FloatingIp[]>([]);
	let interfaces = $state<PortInfo[]>([]);
	let volumes = $state<VolumeAttachment[]>([]);
	let allSecurityGroups = $state<SecurityGroup[]>([]);
	let availableVolumes = $state<VolumeInfo[]>([]);
	let availableNetworks = $state<NetworkInfo[]>([]);
	let ownerDisplay = $state('');
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);
	let actioning = $state<string | null>(null);
	// Console log
	let showLog = $state(false);
	let consoleLog = $state('');
	let logLoading = $state(false);
	let logFull = $state(false);
	let logPreEl = $state<HTMLPreElement | null>(null);
	// Volume panel
	let showAttachVolume = $state(false);
	let attachMode = $state<'existing' | 'new'>('existing');
	let selectedVolumeId = $state('');
	let newVolName = $state('');
	let newVolSize = $state(20);
	// Interface panel
	let showAddInterface = $state(false);
	let selectedNetId = $state('');
	// Security groups
	let sgEditPortId = $state<string | null>(null);
	let sgEditSelected = $state<string[]>([]);
	let expandedSgRules = $state<Set<string>>(new Set());

	function toggleSgRules(sgId: string) {
		const next = new Set(expandedSgRules);
		next.has(sgId) ? next.delete(sgId) : next.add(sgId);
		expandedSgRules = next;
	}

	function formatRule(r: any): string {
		const dir = r.direction === 'ingress' ? '인바운드' : '아웃바운드';
		if (!r.protocol) return `${dir} 전체 허용`;
		const proto = (r.protocol as string).toUpperCase();
		let port = '';
		if (r.port_range_min != null && r.port_range_max != null) {
			port = r.port_range_min === r.port_range_max
				? ` ${r.port_range_min}` : ` ${r.port_range_min}-${r.port_range_max}`;
		}
		const remote = r.remote_ip_prefix ? ` ← ${r.remote_ip_prefix}` : '';
		return `${dir} ${proto}${port}${remote}`;
	}

	const statusColor: Record<string, string> = {
		ACTIVE: 'text-green-400 bg-green-900/30',
		BUILD: 'text-yellow-400 bg-yellow-900/30',
		SHUTOFF: 'text-gray-400 bg-gray-800',
		ERROR: 'text-red-400 bg-red-900/30',
		DELETING: 'text-orange-400 bg-orange-900/30',
		SHELVED_OFFLOADED: 'text-purple-400 bg-purple-900/30',
		SHELVED: 'text-purple-400 bg-purple-900/30',
	};

	const strategyLabel: Record<string, string> = {
		prebuilt: '사전 빌드',
		dynamic: '동적 생성',
	};

	$effect(() => {
		if (!instanceId || !$auth.token) return;
		loading = true;
		error = '';
		fetchInstance(instanceId);
	});

	// Console log auto-refresh when visible
	$effect(() => {
		if (!showLog) return;
		const interval = setInterval(() => {
			loadConsoleLog(logFull);
		}, 5000);
		return () => clearInterval(interval);
	});

	// Scroll to bottom when log updates
	$effect(() => {
		if (consoleLog && logPreEl) {
			logPreEl.scrollTop = logPreEl.scrollHeight;
		}
	});

	async function fetchInstance(id: string) {
		loading = true;
		error = '';
		// 관리자가 다른 프로젝트 인스턴스를 볼 때 해당 project_id 사용
		const effectiveProjectId = adminProjectId ?? ($auth.projectId ?? undefined);
		try {
			instance = await api.get<Instance>(
				`/api/instances/${id}`,
				$auth.token ?? undefined,
				effectiveProjectId
			);
			const [fips, ifaces, vols, sgData, allVols, nets, ownerData] = await Promise.all([
				api.get<FloatingIp[]>('/api/networks/floating-ips', $auth.token ?? undefined, effectiveProjectId).catch(() => []),
				api.get<PortInfo[]>(`/api/instances/${id}/interfaces`, $auth.token ?? undefined, effectiveProjectId).catch(() => []),
				api.get<VolumeAttachment[]>(`/api/instances/${id}/volumes`, $auth.token ?? undefined, effectiveProjectId).catch(() => []),
				api.get<{ ports: PortInfo[]; security_groups: SecurityGroup[] }>(`/api/instances/${id}/security-groups`, $auth.token ?? undefined, effectiveProjectId).catch(() => ({ ports: [], security_groups: [] })),
				api.get<VolumeInfo[]>('/api/volumes', $auth.token ?? undefined, effectiveProjectId).catch(() => []),
				api.get<NetworkInfo[]>('/api/networks', $auth.token ?? undefined, effectiveProjectId).catch(() => []),
				api.get<{ display: string }>(`/api/instances/${id}/owner`, $auth.token ?? undefined, effectiveProjectId).catch(() => ({ display: '' })),
			]);
			const instIps = new Set(instance.ip_addresses.filter(ip => ip.type === 'floating').map(ip => ip.addr));
			floatingIps = fips.filter(f => instIps.has(f.floating_ip_address));
			interfaces = ifaces;
			volumes = vols;
			allSecurityGroups = sgData.security_groups;
			const attachedIds = new Set(vols.map(v => v.volume_id));
			availableVolumes = allVols.filter(v => v.status === 'available' && !attachedIds.has(v.id));
			availableNetworks = nets.filter(n => !n.is_external);
			ownerDisplay = ownerData.display || '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function loadConsoleLog(full = false) {
		if (!instance) return;
		logLoading = true;
		const length = full ? 0 : 200;
		try {
			const data = await api.get<{ output: string }>(
				`/api/instances/${instance.id}/log?length=${length}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			consoleLog = data.output || '(로그 없음)';
		} catch {
			consoleLog = '로그를 가져올 수 없습니다';
		} finally {
			logLoading = false;
		}
	}

	async function toggleLog() {
		showLog = !showLog;
		if (showLog) {
			await loadConsoleLog(logFull);
		}
	}

	async function toggleFullLog() {
		logFull = !logFull;
		await loadConsoleLog(logFull);
	}

	async function openConsole() {
		if (!instance) return;
		try {
			const data = await api.get<{ url: string }>(
				`/api/instances/${instance.id}/console`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			window.open(data.url, '_blank');
		} catch {
			alert('콘솔 URL을 가져올 수 없습니다');
		}
	}

	async function performAction(action: 'start' | 'stop' | 'reboot' | 'shelve' | 'unshelve') {
		if (!instance) return;
		const labels: Record<string, string> = { start: '시작', stop: '정지', reboot: '재부팅', shelve: '보관', unshelve: '보관 해제' };
		if (!confirm(`인스턴스를 ${labels[action]}하시겠습니까?`)) return;
		actioning = action;
		try {
			await api.post(
				`/api/instances/${instance.id}/${action}`,
				{},
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchInstance(instance.id);
		} catch (e) {
			alert(`${labels[action]} 실패: ` + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function deleteInstance() {
		if (!instance) return;
		if (!confirm(`"${instance.name}" 인스턴스를 삭제하시겠습니까?\n파일 스토리지와 볼륨도 함께 삭제됩니다.`))
			return;
		deleting = true;
		try {
			await api.delete(
				`/api/instances/${instance.id}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			if (onClose) onClose();
			else goto('/dashboard/compute/instances');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}

	async function assignFloatingIp() {
		if (!instance) return;
		actioning = 'fip-assign';
		try {
			await api.post(
				`/api/instances/${instance.id}/floating-ip`,
				{},
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchInstance(instance.id);
		} catch (e) {
			alert('Floating IP 할당 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function releaseFloatingIp() {
		if (!confirm('Floating IP를 해제하고 삭제하시겠습니까?')) return;
		actioning = 'fip-release';
		try {
			await api.delete(
				`/api/instances/${instance!.id}/floating-ip`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchInstance(instance!.id);
		} catch (e) {
			alert('Floating IP 해제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function attachVolume() {
		if (!instance || !selectedVolumeId) return;
		actioning = 'attach-vol';
		try {
			await api.post(
				`/api/instances/${instance.id}/volumes`,
				{ volume_id: selectedVolumeId },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			showAttachVolume = false;
			selectedVolumeId = '';
			await fetchInstance(instance.id);
		} catch (e) {
			alert('볼륨 연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function createAndAttachVolume() {
		if (!instance || !newVolName.trim() || newVolSize < 1) return;
		actioning = 'create-vol';
		try {
			const vol = await api.post<VolumeInfo>(
				'/api/volumes',
				{ name: newVolName.trim(), size_gb: newVolSize },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await api.post(
				`/api/instances/${instance.id}/volumes`,
				{ volume_id: vol.id },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			showAttachVolume = false;
			newVolName = '';
			newVolSize = 20;
			await fetchInstance(instance.id);
		} catch (e) {
			alert('볼륨 생성/연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function detachVolume(volumeId: string) {
		if (!instance) return;
		if (!confirm('볼륨을 분리하시겠습니까?')) return;
		actioning = 'detach-' + volumeId;
		try {
			await api.delete(
				`/api/instances/${instance.id}/volumes/${volumeId}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchInstance(instance.id);
		} catch (e) {
			alert('볼륨 분리 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function attachInterface() {
		if (!instance || !selectedNetId) return;
		actioning = 'attach-iface';
		try {
			await api.post(
				`/api/instances/${instance.id}/interfaces`,
				{ net_id: selectedNetId },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			showAddInterface = false;
			selectedNetId = '';
			await fetchInstance(instance.id);
		} catch (e) {
			alert('인터페이스 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function detachInterface(portId: string) {
		if (!instance) return;
		if (!confirm('인터페이스를 제거하시겠습니까?')) return;
		actioning = 'detach-iface-' + portId;
		try {
			await api.delete(
				`/api/instances/${instance.id}/interfaces/${portId}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchInstance(instance.id);
		} catch (e) {
			alert('인터페이스 제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	function openSgEdit(port: PortInfo) {
		sgEditPortId = port.id;
		sgEditSelected = [...port.security_group_ids];
	}

	function toggleSg(sgId: string) {
		if (sgEditSelected.includes(sgId)) {
			sgEditSelected = sgEditSelected.filter(id => id !== sgId);
		} else {
			sgEditSelected = [...sgEditSelected, sgId];
		}
	}

	async function saveSgEdit() {
		if (!instance || !sgEditPortId) return;
		actioning = 'sg-' + sgEditPortId;
		try {
			await api.post(
				`/api/instances/${instance.id}/ports/${sgEditPortId}/security-groups`,
				{ security_group_ids: sgEditSelected },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			sgEditPortId = null;
			await fetchInstance(instance.id);
		} catch (e) {
			alert('보안 그룹 업데이트 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	function formatDate(dt: string | null) {
		if (!dt) return '-';
		return new Date(dt).toLocaleString('ko-KR');
	}

	function sgNameById(id: string): string {
		return allSecurityGroups.find(sg => sg.id === id)?.name ?? id.slice(0, 8) + '...';
	}

	function networkNameById(id: string): string {
		return availableNetworks.find(n => n.id === id)?.name ?? id.slice(0, 12) + '...';
	}

	// 마이그레이션 (관리자 전용)
	let showMigrateModal = $state(false);
	let migrateType = $state<'live' | 'cold'>('live');
	let migrateHosts = $state<{ name: string; state: string; status: string }[]>([]);
	let migrateHost = $state('');
	let migrateLoading = $state(false);
	let migrateError = $state('');

	async function openMigrateModal(type: 'live' | 'cold') {
		migrateType = type;
		migrateHost = '';
		migrateError = '';
		migrateHosts = [];
		showMigrateModal = true;
		try {
			migrateHosts = await api.get<{ name: string; state: string; status: string }[]>(
				'/api/admin/compute-hosts',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
		} catch {
			migrateHosts = [];
		}
	}

	async function doMigrate() {
		if (!instance) return;
		migrateLoading = true;
		migrateError = '';
		try {
			if (migrateType === 'live') {
				await api.post(
					`/api/admin/instances/${instance.id}/live-migrate`,
					{ host: migrateHost || null, block_migration: 'auto' },
					$auth.token ?? undefined,
					$auth.projectId ?? undefined
				);
			} else {
				await api.post(
					`/api/admin/instances/${instance.id}/cold-migrate`,
					{},
					$auth.token ?? undefined,
					$auth.projectId ?? undefined
				);
			}
			showMigrateModal = false;
			await fetchInstance(instance.id);
		} catch (e) {
			migrateError = e instanceof ApiError ? e.message : '마이그레이션 실패';
		} finally {
			migrateLoading = false;
		}
	}

	async function confirmResize() {
		if (!instance) return;
		if (!confirm('리사이즈를 확인하시겠습니까?')) return;
		actioning = 'confirm-resize';
		try {
			await api.post(
				`/api/admin/instances/${instance.id}/confirm-resize`,
				{},
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchInstance(instance.id);
		} catch (e) {
			alert('리사이즈 확인 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}
</script>

<div class="p-8">
	<!-- 헤더 -->
	<div class="mb-6 flex items-center justify-between">
		{#if onClose}
			<button onclick={onClose} class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
				✕ 닫기
			</button>
		{:else}
			<a href="/dashboard/compute/instances" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
				← 인스턴스
			</a>
		{/if}
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={6} />
	{:else if instance}
		<div class="flex items-start justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-white">{instance.name}</h1>
				<span
					class="mt-2 inline-block px-2 py-0.5 rounded text-xs font-medium {statusColor[instance.status] ?? 'text-gray-400 bg-gray-800'}"
				>
					{instance.status}
				</span>
			</div>
			<div class="flex flex-wrap gap-2 justify-end">
				{#if instance.status === 'SHUTOFF'}
					<button
						onclick={() => performAction('start')}
						disabled={!!actioning}
						class="text-green-400 hover:text-green-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-green-900 hover:border-green-700 disabled:border-gray-700 transition-colors"
					>
						{actioning === 'start' ? '시작 중...' : '시작'}
					</button>
				{/if}
				{#if instance.status === 'SHELVED_OFFLOADED' || instance.status === 'SHELVED'}
					<button
						onclick={() => performAction('unshelve')}
						disabled={!!actioning}
						class="text-green-400 hover:text-green-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-green-900 hover:border-green-700 disabled:border-gray-700 transition-colors"
					>
						{actioning === 'unshelve' ? '보관 해제 중...' : '보관 해제'}
					</button>
				{/if}
				{#if instance.status === 'ACTIVE'}
					<button
						onclick={openConsole}
						class="text-gray-300 hover:text-white text-sm px-3 py-1.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
					>
						콘솔 열기
					</button>
					<button
						onclick={() => performAction('stop')}
						disabled={!!actioning}
						class="text-yellow-400 hover:text-yellow-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-yellow-900 hover:border-yellow-700 disabled:border-gray-700 transition-colors"
					>
						{actioning === 'stop' ? '정지 중...' : '정지'}
					</button>
					<button
						onclick={() => performAction('reboot')}
						disabled={!!actioning}
						class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors"
					>
						{actioning === 'reboot' ? '재부팅 중...' : '재부팅'}
					</button>
				{/if}
				{#if instance.status === 'ACTIVE' || instance.status === 'SHUTOFF'}
					<button
						onclick={() => performAction('shelve')}
						disabled={!!actioning}
						class="text-purple-400 hover:text-purple-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-purple-900 hover:border-purple-700 disabled:border-gray-700 transition-colors"
					>
						{actioning === 'shelve' ? '보관 중...' : '보관'}
					</button>
				{/if}
				{#if adminProjectId}
					{#if instance.status === 'ACTIVE'}
						<button
							onclick={() => openMigrateModal('live')}
							disabled={!!actioning}
							class="text-cyan-400 hover:text-cyan-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-cyan-900 hover:border-cyan-700 disabled:border-gray-700 transition-colors"
						>
							라이브 마이그레이션
						</button>
					{/if}
					{#if instance.status === 'ACTIVE' || instance.status === 'SHUTOFF'}
						<button
							onclick={() => openMigrateModal('cold')}
							disabled={!!actioning}
							class="text-teal-400 hover:text-teal-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-teal-900 hover:border-teal-700 disabled:border-gray-700 transition-colors"
						>
							콜드 마이그레이션
						</button>
					{/if}
					{#if instance.status === 'VERIFY_RESIZE'}
						<button
							onclick={confirmResize}
							disabled={!!actioning}
							class="text-orange-400 hover:text-orange-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-orange-900 hover:border-orange-700 disabled:border-gray-700 transition-colors"
						>
							{actioning === 'confirm-resize' ? '확인 중...' : '리사이즈 확인'}
						</button>
					{/if}
				{/if}
				<button
					onclick={deleteInstance}
					disabled={deleting}
					class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
				>
					{deleting ? '삭제 중...' : '삭제'}
				</button>
			</div>
		</div>

		<!-- 기본 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">기본 정보</h2>
			<dl class="grid grid-cols-2 gap-x-8 gap-y-3">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">ID</dt>
					<dd class="text-sm text-gray-300 font-mono">{instance.id}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">생성일</dt>
					<dd class="text-sm text-gray-300">{formatDate(instance.created_at)}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">이미지</dt>
					<dd class="text-sm text-gray-300">{instance.image_name ?? instance.image_id ?? '볼륨에서 부팅'}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">플레이버</dt>
					<dd class="text-sm text-gray-300">{instance.flavor_name ?? instance.flavor_id ?? '-'}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">키페어</dt>
					<dd class="text-sm text-gray-300 font-mono">{instance.key_name ?? '-'}</dd>
				</div>
				{#if ownerDisplay}
					<div class="overflow-hidden">
						<dt class="text-xs text-gray-500 mb-0.5">생성자</dt>
						<dd class="text-sm text-gray-300 font-mono truncate max-w-full" title={ownerDisplay}>{ownerDisplay}</dd>
					</div>
				{/if}
				<div class="col-span-2">
					<dt class="text-xs text-gray-500 mb-1.5">IP 주소</dt>
					<dd class="flex flex-col gap-1.5">
						{#if fixedIpsList.length === 0 && floatingIpsList.length === 0}
							<span class="text-sm text-gray-500">-</span>
						{/if}
						{#each fixedIpsList as fip}
							{@const paired = floatingIpsList.find(fl => fl.network_name === fip.network_name)}
							<div class="flex items-center gap-1.5 flex-wrap">
								<span class="text-sm font-mono text-gray-300 bg-gray-800 px-2 py-0.5 rounded">{fip.addr}</span>
								<span class="text-xs text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded">fixed</span>
								{#if paired}
									<span class="text-sm font-mono text-green-300 bg-gray-800 px-2 py-0.5 rounded">{paired.addr}</span>
									<span class="text-xs text-green-500 bg-green-900/20 px-1.5 py-0.5 rounded">floating</span>
								{/if}
								{#if fip.network_name}
									<span class="text-xs text-gray-500">{fip.network_name}</span>
								{/if}
							</div>
						{/each}
					</dd>
				</div>
			</dl>
		</div>

		<!-- 콘솔 로그 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">콘솔 로그</h2>
				<div class="flex gap-2 items-center">
					{#if showLog}
						<span class="text-xs text-gray-600">5초마다 자동 갱신</span>
						<button
							onclick={toggleFullLog}
							class="text-xs {logFull ? 'text-yellow-400 border-yellow-900' : 'text-gray-400 border-gray-700'} hover:text-gray-200 px-2 py-1 border hover:border-gray-500 rounded transition-colors"
						>
							{logFull ? '최근 200줄' : '전체 로그'}
						</button>
						<button
							onclick={() => loadConsoleLog(logFull)}
							disabled={logLoading}
							class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 hover:border-gray-500 rounded transition-colors disabled:text-gray-600"
						>
							{logLoading ? '로딩...' : '새로고침'}
						</button>
					{/if}
					<button
						onclick={toggleLog}
						class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
					>
						{showLog ? '닫기' : '로그 보기'}
					</button>
				</div>
			</div>
			{#if showLog}
				<pre
					bind:this={logPreEl}
					class="bg-gray-950 border border-gray-800 rounded p-3 text-xs text-gray-300 font-mono overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap"
				>{logLoading && !consoleLog ? '로딩 중...' : consoleLog}</pre>
			{/if}
		</div>

		<!-- Floating IP 관리 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Floating IP</h2>
				{#if floatingIps.length === 0}
					<button
						onclick={assignFloatingIp}
						disabled={actioning === 'fip-assign'}
						class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700"
					>
						{actioning === 'fip-assign' ? '할당 중...' : '+ Floating IP 요청'}
					</button>
				{/if}
			</div>

			{#if floatingIps.length === 0}
				<p class="text-sm text-gray-500">연결된 Floating IP 없음</p>
			{:else}
				<div class="space-y-2">
					{#each floatingIps as fip}
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<span class="font-mono text-sm text-green-300">{fip.floating_ip_address}</span>
								{#if fip.fixed_ip_address}
									<span class="text-xs text-gray-500">→ {fip.fixed_ip_address}</span>
								{/if}
							</div>
							<button
								onclick={releaseFloatingIp}
								disabled={actioning === 'fip-release'}
								class="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600"
							>
								{actioning === 'fip-release' ? '해제 중...' : '해제 및 삭제'}
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- 인터페이스 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">인터페이스</h2>
				<button
					onclick={() => { showAddInterface = !showAddInterface; selectedNetId = ''; }}
					class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
				>
					{showAddInterface ? '닫기' : '+ 인터페이스 추가'}
				</button>
			</div>

			{#if showAddInterface}
				<div class="mb-4 bg-gray-800 rounded-lg p-4">
					<p class="text-xs text-gray-400 mb-2">연결할 네트워크 선택</p>
					<div class="flex gap-2">
						<select
							bind:value={selectedNetId}
							class="flex-1 bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
						>
							<option value="">네트워크 선택...</option>
							{#each availableNetworks as net}
								<option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
							{/each}
						</select>
						<button
							onclick={attachInterface}
							disabled={!selectedNetId || actioning === 'attach-iface'}
							class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700"
						>
							{actioning === 'attach-iface' ? '추가 중...' : '추가'}
						</button>
					</div>
				</div>
			{/if}

			{#if interfaces.length === 0}
				<p class="text-sm text-gray-500">인터페이스 정보 없음</p>
			{:else}
				<div class="space-y-4">
					{#each interfaces as iface}
						<div class="bg-gray-800/50 rounded-lg p-4">
							<div class="flex items-start justify-between mb-3">
								<div class="grid grid-cols-2 gap-x-6 gap-y-2 flex-1">
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">포트 ID</dt>
										<dd class="text-xs text-gray-300 font-mono">{iface.id}</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">MAC 주소</dt>
										<dd class="text-xs text-gray-300 font-mono">{iface.mac_address}</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">네트워크</dt>
										<dd class="text-xs text-gray-300">{networkNameById(iface.network_id)}</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">상태</dt>
										<dd class="text-xs {iface.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{iface.status}</dd>
									</div>
									<div class="col-span-2">
										<dt class="text-xs text-gray-500 mb-1">IP 주소</dt>
										<dd class="flex flex-wrap gap-1.5">
											{#each iface.fixed_ips as fip}
												<span class="text-xs font-mono text-gray-300 bg-gray-700 px-1.5 py-0.5 rounded">{fip.ip_address}</span>
											{/each}
										</dd>
									</div>
								</div>
								<button
									onclick={() => detachInterface(iface.id)}
									disabled={!!actioning}
									class="ml-4 text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600 shrink-0"
								>
									{actioning === 'detach-iface-' + iface.id ? '제거 중...' : '제거'}
								</button>
							</div>
							<!-- 보안 그룹 -->
							<div>
								<div class="flex items-center justify-between mb-1.5">
									<dt class="text-xs text-gray-500">보안 그룹</dt>
									<button
										onclick={() => openSgEdit(iface)}
										class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
									>
										편집
									</button>
								</div>
								{#if sgEditPortId === iface.id}
									<div class="bg-gray-700 rounded p-3 mt-2">
										<p class="text-xs text-gray-500 mb-2">이 프로젝트의 보안 그룹</p>
										<div class="space-y-1.5 mb-3 max-h-56 overflow-y-auto">
											{#each allSecurityGroups as sg}
												<div>
													<label class="flex items-center gap-2 cursor-pointer">
														<input
															type="checkbox"
															checked={sgEditSelected.includes(sg.id)}
															onchange={() => toggleSg(sg.id)}
															class="accent-blue-500"
														/>
														<span class="text-xs text-gray-300">{sg.name}</span>
														{#if sg.description}
															<span class="text-xs text-gray-500 truncate max-w-[100px]">— {sg.description}</span>
														{/if}
														<button
															type="button"
															onclick={() => toggleSgRules(sg.id)}
															class="text-xs text-gray-600 hover:text-gray-400 ml-auto shrink-0 transition-colors"
														>
															{expandedSgRules.has(sg.id) ? '▾' : '▸'} {sg.rules.length}개 규칙
														</button>
													</label>
													{#if expandedSgRules.has(sg.id)}
														<div class="ml-5 mt-1 mb-1 space-y-0.5 pl-2 border-l border-gray-700">
															{#each sg.rules as rule}
																<div class="text-xs text-gray-500 font-mono">{formatRule(rule)}</div>
															{/each}
															{#if sg.rules.length === 0}
																<div class="text-xs text-gray-600 italic">규칙 없음</div>
															{/if}
														</div>
													{/if}
												</div>
											{/each}
										</div>
										<div class="flex gap-2">
											<button
												onclick={saveSgEdit}
												disabled={actioning === 'sg-' + iface.id}
												class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600"
											>
												{actioning === 'sg-' + iface.id ? '저장 중...' : '저장'}
											</button>
											<button
												onclick={() => { sgEditPortId = null; }}
												class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 hover:border-gray-500 rounded transition-colors"
											>
												취소
											</button>
										</div>
									</div>
								{:else}
									<dd class="flex flex-wrap gap-1.5">
										{#if iface.security_group_ids.length === 0}
											<span class="text-xs text-gray-500">없음</span>
										{:else}
											{#each iface.security_group_ids as sgId}
												<span class="text-xs text-purple-300 bg-purple-900/30 px-1.5 py-0.5 rounded">{sgNameById(sgId)}</span>
											{/each}
										{/if}
									</dd>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- 볼륨 관리 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">볼륨</h2>
				<button
					onclick={() => { showAttachVolume = !showAttachVolume; selectedVolumeId = ''; newVolName = ''; newVolSize = 20; }}
					class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
				>
					{showAttachVolume ? '닫기' : '+ 볼륨 연결'}
				</button>
			</div>

			{#if showAttachVolume}
				<div class="mb-4 bg-gray-800 rounded-lg p-4">
					<div class="flex gap-1 mb-3">
						<button
							onclick={() => { attachMode = 'existing'; }}
							class="text-xs px-2 py-1 rounded border transition-colors {attachMode === 'existing' ? 'text-blue-300 border-blue-700 bg-blue-900/20' : 'text-gray-400 border-gray-700 hover:text-gray-200'}"
						>
							기존 볼륨
						</button>
						<button
							onclick={() => { attachMode = 'new'; }}
							class="text-xs px-2 py-1 rounded border transition-colors {attachMode === 'new' ? 'text-blue-300 border-blue-700 bg-blue-900/20' : 'text-gray-400 border-gray-700 hover:text-gray-200'}"
						>
							새 볼륨 생성
						</button>
					</div>

					{#if attachMode === 'existing'}
						{#if availableVolumes.length === 0}
							<p class="text-sm text-gray-500">연결 가능한 볼륨이 없습니다. "새 볼륨 생성"을 이용하세요.</p>
						{:else}
							<div class="flex gap-2">
								<select
									bind:value={selectedVolumeId}
									class="flex-1 bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
								>
									<option value="">볼륨 선택...</option>
									{#each availableVolumes as vol}
										<option value={vol.id}>{vol.name || vol.id.slice(0, 8)} ({vol.size}GB)</option>
									{/each}
								</select>
								<button
									onclick={attachVolume}
									disabled={!selectedVolumeId || actioning === 'attach-vol'}
									class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700"
								>
									{actioning === 'attach-vol' ? '연결 중...' : '연결'}
								</button>
							</div>
						{/if}
					{:else}
						<div class="space-y-2">
							<div class="flex gap-2">
								<input
									bind:value={newVolName}
									type="text"
									placeholder="볼륨 이름"
									class="flex-1 bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
								/>
								<input
									bind:value={newVolSize}
									type="number"
									min="1"
									placeholder="크기(GB)"
									class="w-24 bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
								/>
								<button
									onclick={createAndAttachVolume}
									disabled={!newVolName.trim() || newVolSize < 1 || actioning === 'create-vol'}
									class="text-xs text-green-400 hover:text-green-300 px-3 py-1.5 border border-green-900 hover:border-green-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700 whitespace-nowrap"
								>
									{actioning === 'create-vol' ? '생성 중...' : '생성 및 연결'}
								</button>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			{#if volumes.length === 0}
				<p class="text-sm text-gray-500">연결된 볼륨 없음</p>
			{:else}
				<div class="space-y-2">
					{#each volumes as vol}
						<div class="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
							<div class="flex items-center gap-4">
								<span class="text-xs font-mono text-blue-400 hover:text-blue-300">
									<a href="/dashboard/volumes/{vol.volume_id}">{vol.name || vol.volume_id.slice(0, 12) + '...'}</a>
								</span>
								{#if vol.size}
									<span class="text-xs text-gray-500">{vol.size}GB</span>
								{/if}
								<span class="text-xs font-mono text-gray-500">{vol.device}</span>
								{#if vol.status}
									<span class="text-xs {vol.status === 'in-use' ? 'text-green-400' : 'text-gray-400'}">{vol.status}</span>
								{/if}
							</div>
							<button
								onclick={() => detachVolume(vol.volume_id)}
								disabled={actioning === 'detach-' + vol.volume_id}
								class="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600"
							>
								{actioning === 'detach-' + vol.volume_id ? '분리 중...' : '분리'}
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Afterglow 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Afterglow 정보</h2>
			<dl class="grid grid-cols-2 gap-x-8 gap-y-3">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">전략</dt>
					<dd class="text-sm text-gray-300">
						{instance.union_strategy ? strategyLabel[instance.union_strategy] ?? instance.union_strategy : '-'}
					</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">라이브러리</dt>
					<dd class="flex flex-wrap gap-1">
						{#each instance.union_libraries.filter(Boolean) as lib}
							<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{lib}</span>
						{:else}
							<span class="text-sm text-gray-500">-</span>
						{/each}
					</dd>
				</div>
				{#if instance.union_upper_volume_id}
					<div class="col-span-2">
						<dt class="text-xs text-gray-500 mb-0.5">Upper 볼륨</dt>
						<dd>
							<a
								href="/dashboard/volumes/{instance.union_upper_volume_id}"
								class="text-sm text-blue-400 hover:text-blue-300 font-mono transition-colors"
							>
								{instance.union_upper_volume_id}
							</a>
						</dd>
					</div>
				{/if}
				{#if instance.union_share_ids.filter(Boolean).length > 0}
					<div class="col-span-2">
						<dt class="text-xs text-gray-500 mb-1.5">연결된 파일 스토리지</dt>
						<dd class="flex flex-col gap-1">
							{#each instance.union_share_ids.filter(Boolean) as sid}
								<a
									href="/dashboard/file-storage/{sid}"
									class="text-sm text-blue-400 hover:text-blue-300 font-mono transition-colors"
								>
									{sid}
								</a>
							{/each}
						</dd>
					</div>
				{/if}
			</dl>
		</div>

		<!-- 메타데이터 -->
		{#if Object.keys(instance.metadata).length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">메타데이터</h2>
				<table class="w-full text-sm">
					<tbody>
						{#each Object.entries(instance.metadata) as [k, v]}
							<tr class="border-b border-gray-800/50">
								<td class="py-2 pr-4 text-gray-500 text-xs w-1/3">{k}</td>
								<td class="py-2 text-gray-300 font-mono text-xs break-all">{v}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>

<!-- 마이그레이션 모달 -->
{#if showMigrateModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" role="dialog" onclick={() => { showMigrateModal = false; }} onkeydown={(e) => e.key === 'Escape' && (showMigrateModal = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-1">{migrateType === 'live' ? '라이브 마이그레이션' : '콜드 마이그레이션'}</h2>
			<p class="text-xs text-gray-500 mb-5">{migrateType === 'live' ? '인스턴스 실행 중에 다른 호스트로 이동합니다.' : '인스턴스를 종료하고 다른 호스트로 이동합니다.'}</p>
			{#if migrateError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{migrateError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">대상 호스트 <span class="text-gray-600">(선택 안 하면 자동)</span></label>
					<select bind:value={migrateHost} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
						<option value="">자동 선택</option>
						{#each migrateHosts as h}
							<option value={h.name}>{h.name}</option>
						{/each}
					</select>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showMigrateModal = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={doMigrate} disabled={migrateLoading} class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{migrateLoading ? '마이그레이션 중...' : '마이그레이션'}
				</button>
			</div>
		</div>
	</div>
{/if}
