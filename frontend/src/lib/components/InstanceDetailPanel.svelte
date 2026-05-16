<script lang="ts">
	import { setContext } from 'svelte';
	import { auth, isAdmin } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import MetricsPanel from '$lib/components/instance/MetricsPanel.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import DetailHeader from '$lib/components/ui/DetailHeader.svelte';
	import { createInstanceDetailStore } from '$lib/stores/instanceDetail.svelte';
	import type { PortInfo } from '$lib/types/resources';

	interface Props {
		instanceId: string;
		onClose?: () => void;
		adminProjectId?: string | null;
	}

	let { instanceId, onClose, adminProjectId = null }: Props = $props();

	const s = createInstanceDetailStore({
		instanceId: () => instanceId,
		effectiveProjectId: () => adminProjectId ?? ($auth.projectId ?? undefined),
		adminMode: () => !!adminProjectId,
		onDelete: () => {
			if (onClose) onClose();
			else goto('/dashboard/compute/instances');
		},
	});

	setContext('instance-detail', s);

	// UI-only state
	let showLog = $state(false);
	let logPreEl = $state<HTMLPreElement | null>(null);
	let showAttachVolume = $state(false);
	let attachMode = $state<'existing' | 'new'>('existing');
	let selectedVolumeId = $state('');
	let newVolName = $state('');
	let newVolSize = $state(20);
	let showAddInterface = $state(false);
	let selectedNetId = $state('');
	let sgEditPortId = $state<string | null>(null);
	let sgEditSelected = $state<string[]>([]);
	let expandedSgRules = $state<Set<string>>(new Set());
	let showResizeModal = $state(false);
	let resizeFlavorId = $state('');
	let showPasswordModal = $state(false);
	let newPassword = $state('');
	let confirmPassword = $state('');
	let passwordError = $state('');
	let showMigrateModal = $state(false);
	let migrateType = $state<'live' | 'cold'>('live');
	let migrateHost = $state('');

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

	// Initial load when instanceId or token changes
	$effect(() => {
		if (!instanceId || !$auth.token) return;
		s.fetchInstance(instanceId);
	});

	// Scroll to bottom when console log updates
	$effect(() => {
		if (s.consoleLog && logPreEl) {
			logPreEl.scrollTop = logPreEl.scrollHeight;
		}
	});

	// UI-only handlers
	function toggleSgRules(sgId: string) {
		const next = new Set(expandedSgRules);
		next.has(sgId) ? next.delete(sgId) : next.add(sgId);
		expandedSgRules = next;
	}

	function toggleSg(sgId: string) {
		if (sgEditSelected.includes(sgId)) {
			sgEditSelected = sgEditSelected.filter(id => id !== sgId);
		} else {
			sgEditSelected = [...sgEditSelected, sgId];
		}
	}

	function openSgEdit(port: PortInfo) {
		sgEditPortId = port.id;
		sgEditSelected = [...port.security_group_ids];
	}

	async function handleSaveSgEdit() {
		if (!sgEditPortId) return;
		await s.saveSgEdit(sgEditPortId, sgEditSelected);
		sgEditPortId = null;
	}

	async function toggleLog() {
		showLog = !showLog;
		s.consolePollAr.active = showLog;
		if (showLog) await s.loadConsoleLog(s.logFull);
	}

	async function openResizeModal() {
		resizeFlavorId = '';
		s.resizeError = '';
		showResizeModal = true;
		await s.loadResizeFlavors();
	}

	async function handleDoResize() {
		const ok = await s.doResize(resizeFlavorId);
		if (ok) showResizeModal = false;
	}

	function openPasswordModal() {
		newPassword = '';
		confirmPassword = '';
		passwordError = '';
		showPasswordModal = true;
	}

	async function handleDoSetPassword() {
		if (newPassword !== confirmPassword) {
			passwordError = '패스워드가 일치하지 않습니다';
			return;
		}
		if (newPassword.length < 8) {
			passwordError = '패스워드는 8자 이상이어야 합니다';
			return;
		}
		passwordError = '';
		const err = await s.doSetPassword(newPassword);
		if (err) {
			passwordError = err;
		} else {
			showPasswordModal = false;
			newPassword = '';
			confirmPassword = '';
		}
	}

	async function openMigrateModal(type: 'live' | 'cold') {
		migrateType = type;
		migrateHost = '';
		s.migrateError = '';
		showMigrateModal = true;
		await s.loadMigrateHosts();
	}

	async function handleDoMigrate() {
		const ok = await s.doMigrate(migrateType, migrateHost);
		if (ok) showMigrateModal = false;
	}

	async function handleAttachVolume() {
		await s.attachVolume(selectedVolumeId);
		showAttachVolume = false;
		selectedVolumeId = '';
	}

	async function handleCreateAndAttach() {
		await s.createAndAttachVolume(newVolName.trim(), newVolSize);
		showAttachVolume = false;
		newVolName = '';
		newVolSize = 20;
	}

	async function handleAttachInterface() {
		await s.attachInterface(selectedNetId);
		showAddInterface = false;
		selectedNetId = '';
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
		<AutoRefreshControl
			bind:active={s.detailPollAr.active}
			bind:intervalSeconds={s.detailPollAr.intervalSeconds}
			intervalOptions={s.detailPollAr.intervalOptions}
			refreshing={s.refreshing}
			onManualRefresh={s.manualRefresh}
		/>
	</div>

	{#if s.error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{s.error}
		</div>
	{:else if s.loading}
		<LoadingSkeleton variant="card" rows={6} />
	{:else if s.instance}
		<DetailHeader title={s.instance.name} status={s.instance.status} size="lg">
			{#snippet meta()}
				{#if s.instance!.status === 'ERROR' && s.instance!.fault?.message && adminProjectId}
					<div class="p-3 rounded-lg bg-red-900/30 border border-red-800/40 text-red-300 text-sm max-w-xl">
						<div class="font-medium mb-1 text-xs text-red-400">오류 상세 (관리자)</div>
						<div class="text-xs opacity-90 break-words">{s.instance!.fault!.message}</div>
					</div>
				{/if}
			{/snippet}
			{#snippet actions()}
				{#if s.instance!.status === 'SHUTOFF'}
					<button
						onclick={() => s.performAction('start')}
						disabled={!!s.actioning}
						class="text-green-400 hover:text-green-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-green-900 hover:border-green-700 disabled:border-gray-700 transition-colors"
					>
						{s.actioning === 'start' ? '시작 중...' : '시작'}
					</button>
				{/if}
				{#if s.instance!.status === 'SHELVED_OFFLOADED' || s.instance!.status === 'SHELVED'}
					<button
						onclick={() => s.performAction('unshelve')}
						disabled={!!s.actioning}
						class="text-green-400 hover:text-green-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-green-900 hover:border-green-700 disabled:border-gray-700 transition-colors"
					>
						{s.actioning === 'unshelve' ? '보관 해제 중...' : '보관 해제'}
					</button>
				{/if}
				{#if s.instance!.status === 'ACTIVE'}
					<button
						onclick={s.openConsole}
						class="text-gray-300 hover:text-white text-sm px-3 py-1.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
					>
						콘솔 열기
					</button>
					<button
						onclick={() => s.performAction('stop')}
						disabled={!!s.actioning}
						class="text-yellow-400 hover:text-yellow-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-yellow-900 hover:border-yellow-700 disabled:border-gray-700 transition-colors"
					>
						{s.actioning === 'stop' ? '정지 중...' : '정지'}
					</button>
					<button
						onclick={() => s.performAction('reboot')}
						disabled={!!s.actioning}
						class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors"
					>
						{s.actioning === 'reboot' ? '재부팅 중...' : '재부팅'}
					</button>
				{/if}
				{#if s.instance!.status === 'ACTIVE' || s.instance!.status === 'SHUTOFF'}
					<button
						onclick={() => s.performAction('shelve')}
						disabled={!!s.actioning}
						class="text-purple-400 hover:text-purple-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-purple-900 hover:border-purple-700 disabled:border-gray-700 transition-colors"
					>
						{s.actioning === 'shelve' ? '보관 중...' : '보관'}
					</button>
				{/if}
				{#if adminProjectId}
					{#if s.instance!.status === 'ACTIVE'}
						<button
							onclick={() => openMigrateModal('live')}
							disabled={!!s.actioning}
							class="text-cyan-400 hover:text-cyan-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-cyan-900 hover:border-cyan-700 disabled:border-gray-700 transition-colors"
						>
							라이브 마이그레이션
						</button>
					{/if}
					{#if s.instance!.status === 'ACTIVE' || s.instance!.status === 'SHUTOFF'}
						<button
							onclick={() => openMigrateModal('cold')}
							disabled={!!s.actioning}
							class="text-teal-400 hover:text-teal-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-teal-900 hover:border-teal-700 disabled:border-gray-700 transition-colors"
						>
							콜드 마이그레이션
						</button>
						<button
							onclick={openResizeModal}
							disabled={!!s.actioning}
							class="text-violet-400 hover:text-violet-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-violet-900 hover:border-violet-700 disabled:border-gray-700 transition-colors"
						>
							리사이즈
						</button>
					{/if}
					{#if s.instance!.status === 'VERIFY_RESIZE'}
						<button
							onclick={s.confirmResize}
							disabled={!!s.actioning}
							class="text-orange-400 hover:text-orange-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-orange-900 hover:border-orange-700 disabled:border-gray-700 transition-colors"
						>
							{s.actioning === 'confirm-resize' ? '확인 중...' : '리사이즈 확인'}
						</button>
						<button
							onclick={s.revertResize}
							disabled={!!s.actioning}
							class="text-yellow-400 hover:text-yellow-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-yellow-900 hover:border-yellow-700 disabled:border-gray-700 transition-colors"
						>
							{s.actioning === 'revert-resize' ? '취소 중...' : '되돌리기'}
						</button>
					{/if}
					<button
						onclick={openPasswordModal}
						disabled={s.passwordPrecheckLoading || !s.passwordPrecheck?.supported}
						title={s.passwordPrecheck?.reason ?? (s.passwordPrecheckLoading ? '점검 중...' : '')}
						class="text-amber-400 hover:text-amber-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-amber-900 hover:border-amber-700 disabled:border-gray-700 transition-colors"
					>
						{s.passwordPrecheckLoading ? '점검 중...' : '비밀번호 재설정'}
					</button>
				{/if}
				<button
					onclick={s.deleteInstance}
					disabled={s.deleting}
					class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
				>
					{s.deleting ? '삭제 중...' : '삭제'}
				</button>
			{/snippet}
		</DetailHeader>

		<!-- 기본 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">기본 정보</h2>
			<dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-8 gap-y-3">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">ID</dt>
					<dd class="text-sm text-gray-300 font-mono">{s.instance.id}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">생성일</dt>
					<dd class="text-sm text-gray-300">{s.formatDate(s.instance.created_at)}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">이미지</dt>
					<dd class="text-sm text-gray-300">{s.instance.image_name ?? s.instance.image_id ?? '볼륨에서 부팅'}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">플레이버</dt>
					<dd class="text-sm text-gray-300">{s.instance.flavor_name ?? s.instance.flavor_id ?? '-'}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">키페어</dt>
					<dd class="text-sm text-gray-300 font-mono">{s.instance.key_name ?? '-'}</dd>
				</div>
				{#if s.ownerDisplay}
					<div class="overflow-hidden">
						<dt class="text-xs text-gray-500 mb-0.5">생성자</dt>
						<dd class="text-sm text-gray-300 font-mono truncate max-w-full" title={s.ownerDisplay}>{s.ownerDisplay}</dd>
					</div>
				{/if}
				<div class="col-span-2">
					<dt class="text-xs text-gray-500 mb-1.5">IP 주소</dt>
					<dd class="flex flex-col gap-1.5">
						{#if s.fixedIpsList.length === 0 && s.floatingIpsList.length === 0}
							<span class="text-sm text-gray-500">-</span>
						{/if}
						{#each s.fixedIpsList as fip}
							{@const paired = s.floatingIpsList.find(fl => fl.network_name === fip.network_name)}
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

		<!-- 성능 모니터링 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="text-white text-[15px] font-semibold mb-4">성능 모니터링</div>
			<MetricsPanel
				instanceId={s.instance.id}
				isGpu={(s.instance.flavor_name ?? '').toLowerCase().startsWith('gpu.')}
			/>
		</div>

		<!-- 콘솔 로그 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">콘솔 로그</h2>
				<div class="flex gap-2 items-center">
					{#if showLog}
						<span class="text-xs text-gray-600">{s.consolePollAr.intervalSeconds}초마다 자동 갱신</span>
						<button
							onclick={s.toggleFullLog}
							class="text-xs {s.logFull ? 'text-yellow-400 border-yellow-900' : 'text-gray-400 border-gray-700'} hover:text-gray-200 px-2 py-1 border hover:border-gray-500 rounded transition-colors"
						>
							{s.logFull ? '최근 200줄' : '전체 로그'}
						</button>
						<a
							href="/dashboard/compute/instances/{s.instance.id}/console-log"
							target="_blank"
							rel="noopener noreferrer"
							class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 hover:border-gray-500 rounded transition-colors"
							title="새 창에서 전체 로그 보기"
						>
							새 창에서 보기 ↗
						</a>
						<button
							onclick={() => s.loadConsoleLog(s.logFull)}
							disabled={s.logLoading}
							class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 hover:border-gray-500 rounded transition-colors disabled:text-gray-600"
						>
							{s.logLoading ? '로딩...' : '새로고침'}
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
				>{s.logLoading && !s.consoleLog ? '로딩 중...' : s.consoleLog}</pre>
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
							{#each s.availableNetworks as net}
								<option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
							{/each}
						</select>
						<button
							onclick={handleAttachInterface}
							disabled={!selectedNetId || s.actioning === 'attach-iface'}
							class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700"
						>
							{s.actioning === 'attach-iface' ? '추가 중...' : '추가'}
						</button>
					</div>
				</div>
			{/if}

			{#if s.interfaces.length === 0}
				<p class="text-sm text-gray-500">인터페이스 정보 없음</p>
			{:else}
				<div class="space-y-4">
					{#each s.interfaces as iface}
						{@const ifaceFip = s.floatingIps.find(f => f.port_id === iface.id)}
						<div class="bg-gray-800/50 rounded-lg p-4">
							<div class="flex items-start justify-between mb-3">
								<div class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-2 flex-1">
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
										<dd class="text-xs text-gray-300">{s.networkNameById(iface.network_id)}</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">상태</dt>
										<dd class="text-xs {iface.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{iface.status}</dd>
									</div>
									<div class="col-span-2">
										<dt class="text-xs text-gray-500 mb-1">IP 주소</dt>
										<dd class="flex flex-wrap gap-1.5 items-center">
											{#each iface.fixed_ips as fip}
												<span class="text-xs font-mono text-gray-300 bg-gray-700 px-1.5 py-0.5 rounded">{fip.ip_address}</span>
											{/each}
											{#if ifaceFip}
												<span class="text-xs font-mono text-green-300 bg-green-900/20 px-1.5 py-0.5 rounded">{ifaceFip.floating_ip_address}</span>
											{/if}
										</dd>
									</div>
								</div>
								<div class="ml-4 flex flex-col gap-1.5 shrink-0">
									{#if ifaceFip}
										<button
											onclick={() => s.releaseFloatingIp(ifaceFip.id)}
											disabled={!!s.actioning}
											class="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600"
										>
											{s.actioning === 'fip-release-' + ifaceFip.id ? '해제 중...' : 'FIP 해제'}
										</button>
									{:else}
										<button
											onclick={() => s.assignFloatingIp(iface.id)}
											disabled={!!s.actioning}
											class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600"
										>
											{s.actioning === 'fip-assign-' + iface.id ? '할당 중...' : '+ FIP'}
										</button>
									{/if}
									<button
										onclick={() => s.detachInterface(iface.id)}
										disabled={!!s.actioning}
										class="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600"
									>
										{s.actioning === 'detach-iface-' + iface.id ? '제거 중...' : '제거'}
									</button>
								</div>
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
											{#each s.allSecurityGroups as sg}
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
																<div class="text-xs text-gray-500 font-mono">{s.formatRule(rule)}</div>
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
												onclick={handleSaveSgEdit}
												disabled={s.actioning === 'sg-' + iface.id}
												class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600"
											>
												{s.actioning === 'sg-' + iface.id ? '저장 중...' : '저장'}
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
												<span class="text-xs text-purple-300 bg-purple-900/30 px-1.5 py-0.5 rounded">{s.sgNameById(sgId)}</span>
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
						{#if s.availableVolumes.length === 0}
							<p class="text-sm text-gray-500">연결 가능한 볼륨이 없습니다. "새 볼륨 생성"을 이용하세요.</p>
						{:else}
							<div class="flex gap-2">
								<select
									bind:value={selectedVolumeId}
									class="flex-1 bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
								>
									<option value="">볼륨 선택...</option>
									{#each s.availableVolumes as vol}
										<option value={vol.id}>{vol.name || vol.id.slice(0, 8)} ({vol.size}GB)</option>
									{/each}
								</select>
								<button
									onclick={handleAttachVolume}
									disabled={!selectedVolumeId || s.actioning === 'attach-vol'}
									class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700"
								>
									{s.actioning === 'attach-vol' ? '연결 중...' : '연결'}
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
									onclick={handleCreateAndAttach}
									disabled={!newVolName.trim() || newVolSize < 1 || s.actioning === 'create-vol'}
									class="text-xs text-green-400 hover:text-green-300 px-3 py-1.5 border border-green-900 hover:border-green-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700 whitespace-nowrap"
								>
									{s.actioning === 'create-vol' ? '생성 중...' : '생성 및 연결'}
								</button>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			{#if s.volumes.length === 0}
				<p class="text-sm text-gray-500">연결된 볼륨 없음</p>
			{:else}
				<div class="space-y-2">
					{#each s.volumes as vol}
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
								<button
									type="button"
									onclick={() => s.setDeleteOnTermination(vol.volume_id, !vol.delete_on_termination)}
									disabled={s.actioning === 'dot-' + vol.volume_id}
									title="클릭해서 토글"
									class="text-[10px] px-1.5 py-0.5 rounded transition-colors disabled:opacity-50 cursor-pointer
										{vol.delete_on_termination
											? 'text-red-300 bg-red-900/30 hover:bg-red-900/50 border border-red-800/50'
											: 'text-gray-400 bg-gray-800 hover:bg-gray-700 border border-gray-700'}"
								>
									{s.actioning === 'dot-' + vol.volume_id
										? '변경 중...'
										: vol.delete_on_termination
											? '인스턴스 삭제 시 자동 삭제'
											: '유지'}
								</button>
							</div>
							<button
								onclick={() => s.detachVolume(vol.volume_id)}
								disabled={s.actioning === 'detach-' + vol.volume_id}
								class="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600"
							>
								{s.actioning === 'detach-' + vol.volume_id ? '분리 중...' : '분리'}
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Afterglow 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Afterglow 정보</h2>
			<dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-8 gap-y-3">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">전략</dt>
					<dd class="text-sm text-gray-300">
						{s.instance.union_strategy ? strategyLabel[s.instance.union_strategy] ?? s.instance.union_strategy : '-'}
					</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">라이브러리</dt>
					<dd class="flex flex-wrap gap-1">
						{#each s.instance.union_libraries.filter(Boolean) as lib}
							<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{lib}</span>
						{:else}
							<span class="text-sm text-gray-500">-</span>
						{/each}
					</dd>
				</div>
				{#if s.instance.union_upper_volume_id}
					<div class="col-span-2">
						<dt class="text-xs text-gray-500 mb-0.5">Upper 볼륨</dt>
						<dd>
							<a
								href="/dashboard/volumes/{s.instance.union_upper_volume_id}"
								class="text-sm text-blue-400 hover:text-blue-300 font-mono transition-colors"
							>
								{s.instance.union_upper_volume_id}
							</a>
						</dd>
					</div>
				{/if}
				{#if s.instance.union_share_ids.filter(Boolean).length > 0}
					<div class="col-span-2">
						<dt class="text-xs text-gray-500 mb-1.5">연결된 파일 스토리지</dt>
						<dd class="flex flex-col gap-1">
							{#each s.instance.union_share_ids.filter(Boolean) as sid}
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
		{#if Object.keys(s.instance.metadata).length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">메타데이터</h2>
				<table class="w-full text-sm">
					<tbody>
						{#each Object.entries(s.instance.metadata) as [k, v]}
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
			{#if s.migrateError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{s.migrateError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">대상 호스트 <span class="text-gray-600">(선택 안 하면 자동)</span></label>
					<select bind:value={migrateHost} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
						<option value="">자동 선택</option>
						{#each s.migrateHosts as h}
							<option value={h.name}>{h.name}</option>
						{/each}
					</select>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showMigrateModal = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={handleDoMigrate} disabled={s.migrateLoading} class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{s.migrateLoading ? '마이그레이션 중...' : '마이그레이션'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if showPasswordModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" role="dialog" onclick={() => { showPasswordModal = false; }} onkeydown={(e) => e.key === 'Escape' && (showPasswordModal = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="document">
			<h3 class="text-white font-semibold text-lg mb-1">관리자 비밀번호 재설정</h3>
			<p class="text-gray-400 text-sm mb-4">인스턴스: <span class="text-white">{s.instance?.name}</span></p>
			{#if s.passwordPrecheck?.os_admin_user}
				<p class="text-xs text-gray-500 mb-4">대상 계정: <span class="text-amber-400">{s.passwordPrecheck.os_admin_user}</span> (이미지 메타 기준)</p>
			{:else}
				<p class="text-xs text-gray-500 mb-4">대상 계정: 이미지 메타데이터의 <code class="text-amber-400">os_admin_user</code>로 자동 결정</p>
			{/if}
			<div class="bg-yellow-900/20 border border-yellow-800/40 rounded-lg p-3 mb-4 text-xs text-yellow-300">
				QGA가 게스트에 실제로 동작 중이어야 변경이 적용됩니다. 변경 직후 콘솔/SSH로 동작을 확인하세요.
			</div>
			<div class="space-y-3 mb-4">
				<div>
					<label class="block text-sm text-gray-400 mb-1" for="new-password">새 비밀번호</label>
					<input
						id="new-password"
						type="password"
						bind:value={newPassword}
						placeholder="8자 이상"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
					/>
				</div>
				<div>
					<label class="block text-sm text-gray-400 mb-1" for="confirm-password">비밀번호 확인</label>
					<input
						id="confirm-password"
						type="password"
						bind:value={confirmPassword}
						placeholder="동일한 비밀번호 재입력"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
					/>
				</div>
			</div>
			{#if passwordError}
				<p class="text-red-400 text-sm mb-3">{passwordError}</p>
			{/if}
			<div class="bg-gray-800/60 border border-gray-700/40 rounded-lg p-3 mb-4 text-xs text-gray-400">
				<span class="text-gray-300 font-medium">SSH 키 런타임 주입 안내:</span>
				표준 OpenStack은 실행 중 SSH 키 주입을 지원하지 않습니다.
				키페어 사전 등록은 <a href="/dashboard/compute/keypairs" class="text-cyan-400 hover:underline">키페어 관리</a>에서, 비상 복구는 rebuild를 사용하세요.
			</div>
			<div class="flex justify-end gap-3">
				<button onclick={() => { showPasswordModal = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={handleDoSetPassword} disabled={s.passwordPrecheckLoading || !newPassword || !confirmPassword} class="px-4 py-2 bg-amber-700 hover:bg-amber-600 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{s.passwordPrecheckLoading ? '변경 중...' : '변경'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if showResizeModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" role="dialog" onclick={() => { showResizeModal = false; }} onkeydown={(e) => e.key === 'Escape' && (showResizeModal = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-1">인스턴스 리사이즈</h2>
			<p class="text-xs text-gray-500 mb-5">플레이버를 변경합니다. 완료 후 '리사이즈 확인' 또는 '되돌리기'를 선택하세요.</p>
			{#if s.resizeError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{s.resizeError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">새 플레이버</label>
					<select bind:value={resizeFlavorId} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500">
						<option value="">플레이버 선택</option>
						{#each s.resizeFlavors as f}
							<option value={f.id}>{f.name} ({f.vcpus} vCPU / {f.ram >= 1024 ? (f.ram / 1024).toFixed(0) + ' GB' : f.ram + ' MB'} RAM)</option>
						{/each}
					</select>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showResizeModal = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={handleDoResize} disabled={s.resizeLoading || !resizeFlavorId} class="px-4 py-2 bg-violet-700 hover:bg-violet-600 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{s.resizeLoading ? '리사이즈 중...' : '리사이즈'}
				</button>
			</div>
		</div>
	</div>
{/if}
