<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { siteConfig } from '$lib/config/site';
	import { ApiError } from '$lib/api/client';
	import { toast } from '$lib/stores/toast';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { downloadBlobAs } from '$lib/utils/downloadBlob';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import TableShell from '$lib/components/ui/TableShell.svelte';
	import FormModal from '$lib/components/ui/FormModal.svelte';
	import Field from '$lib/components/ui/Field.svelte';
	import TextInput from '$lib/components/ui/TextInput.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import * as vpnApi from '$lib/api/vpn';
	import type { VpnServer, VpnClient } from '$lib/types/vpn';

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);
	const vpnConfigured = $derived($siteConfig.services?.vpn ?? false);

	let servers = $state<VpnServer[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');

	// 서버 생성 모달
	let showCreateModal = $state(false);
	let newServerName = $state('');
	let creating = $state(false);
	let createError = $state('');

	// 상세 패널
	let selectedServerId = $state<string | null>(null);
	const selectedServer = $derived(servers.find((s) => s.id === selectedServerId) ?? null);

	async function fetchServers(opts?: { refresh?: boolean }) {
		try {
			servers = await vpnApi.listServers(token, projectId);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchServers({ refresh: true });
		} finally {
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(() => fetchServers(), {
		storageKey: 'dashboard-network-vpn',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		loading = true;
		untrack(() => fetchServers());
	});

	async function createServer() {
		creating = true;
		createError = '';
		try {
			await vpnApi.createServer(newServerName.trim(), token, projectId);
			showCreateModal = false;
			newServerName = '';
			toast.success('VPN 서버 생성이 시작되었습니다');
			await fetchServers();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteServer(server: VpnServer) {
		if (!(await confirmDialog(`VPN 서버 "${server.name}"을 삭제하시겠습니까?`))) return;
		try {
			await vpnApi.deleteServer(server.id, token, projectId);
			toast.success('VPN 서버 삭제가 시작되었습니다');
			if (selectedServerId === server.id) selectedServerId = null;
			await fetchServers();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	function openPanel(id: string) {
		selectedServerId = id;
	}
	function closePanel() {
		selectedServerId = null;
	}

	// ---- 클라이언트(peer) 관리 ----
	let clients = $state<VpnClient[]>([]);
	let clientsLoading = $state(false);
	let clientsError = $state('');

	async function fetchClients(serverId: string) {
		clientsLoading = true;
		try {
			clients = await vpnApi.listClients(serverId, token, projectId);
			clientsError = '';
		} catch (e) {
			clientsError = e instanceof ApiError ? e.message : '클라이언트 조회 실패';
		} finally {
			clientsLoading = false;
		}
	}

	$effect(() => {
		const id = selectedServerId;
		if (!id) {
			clients = [];
			return;
		}
		untrack(() => fetchClients(id));
	});

	// 상세 패널이 열려있는 동안 서버 상태 + 클라이언트 상태를 함께 갱신
	const panelAr = createAutoRefresh(
		() => {
			if (!selectedServerId) return;
			fetchServers();
			fetchClients(selectedServerId);
		},
		{
			storageKey: 'dashboard-network-vpn-detail',
			defaultActive: true,
			defaultInterval: 15,
			intervalOptions: [10, 15, 30, 60],
			invokeOnMount: false,
		}
	);

	let showClientModal = $state(false);
	let newClientName = $state('');
	let clientCreating = $state(false);
	let clientCreateError = $state('');

	async function createClient() {
		if (!selectedServerId) return;
		clientCreating = true;
		clientCreateError = '';
		try {
			const result = await vpnApi.createClient(
				selectedServerId,
				{ name: newClientName.trim() },
				token,
				projectId
			);
			showClientModal = false;
			newClientName = '';
			toast.success('VPN 클라이언트가 발급되었습니다');
			// 발급 직후 응답에 평문 .conf가 포함되어 있으므로 바로 다운로드 제공
			const blob = new Blob([result.tunnel_conf], { type: 'text/plain' });
			downloadBlobAs(blob, `${result.name}.conf`);
			await fetchClients(selectedServerId);
		} catch (e) {
			clientCreateError = e instanceof ApiError ? e.message : '클라이언트 발급 실패';
		} finally {
			clientCreating = false;
		}
	}

	async function toggleClient(client: VpnClient) {
		if (!selectedServerId) return;
		try {
			await vpnApi.updateClient(
				selectedServerId,
				client.id,
				{ enabled: !client.enabled },
				token,
				projectId
			);
			await fetchClients(selectedServerId);
		} catch (e) {
			toast.error('상태 변경 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	async function deleteClient(client: VpnClient) {
		if (!selectedServerId) return;
		if (!(await confirmDialog(`클라이언트 "${client.name}"을 삭제하시겠습니까?`))) return;
		try {
			await vpnApi.deleteClient(selectedServerId, client.id, token, projectId);
			toast.success('클라이언트가 삭제되었습니다');
			await fetchClients(selectedServerId);
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	let downloadingClientId = $state<string | null>(null);

	async function downloadConfig(client: VpnClient) {
		if (!selectedServerId) return;
		downloadingClientId = client.id;
		try {
			const { blob, filename } = await vpnApi.downloadClientConfig(
				selectedServerId,
				client.id,
				token,
				projectId
			);
			downloadBlobAs(blob, filename);
		} catch (e) {
			toast.error('다운로드 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			downloadingClientId = null;
		}
	}

	function clientStatusLabel(client: VpnClient): string {
		if (!client.enabled) return 'disabled';
		return client.online ? 'ONLINE' : 'OFFLINE';
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '-';
		try {
			return new Date(iso).toLocaleString('ko');
		} catch {
			return iso;
		}
	}
</script>

<FormModal
	bind:open={showCreateModal}
	title="VPN 서버 생성"
	submitLabel="생성"
	submitting={creating}
	onSubmit={createServer}
	onClose={() => { showCreateModal = false; createError = ''; }}
>
	<div class="space-y-4">
		<Field label="이름" help="비워두면 자동으로 생성됩니다">
			<TextInput bind:value={newServerName} placeholder="vpn-gateway" />
		</Field>
		{#if createError}
			<p class="text-sm text-[var(--color-state-danger)]">{createError}</p>
		{/if}
	</div>
</FormModal>

<div class="p-4 md:p-8">
	<PageHeader breadcrumb="NETWORK / VPN" title="WireGuard VPN">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing}
				onManualRefresh={forceRefresh}
			/>
			{#if vpnConfigured}
				<Button onclick={() => { showCreateModal = true; createError = ''; }} variant="accent" size="sm">
					+ VPN 서버 생성
				</Button>
			{/if}
		{/snippet}
	</PageHeader>

	{#if !vpnConfigured}
		<Alert tone="warning" class="mb-4">
			관리자가 아직 VPN 기능을 설정하지 않았습니다. (afterglow.conf [vpn] provider_network_id / image_id 필요)
		</Alert>
	{/if}

	{#if error}
		<Alert tone="danger" class="mb-4">{error}</Alert>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if servers.length === 0}
		<div class="text-center py-20 text-[var(--color-ink-3)]">
			<div class="text-5xl mb-4">🔐</div>
			<div class="text-lg">VPN 서버가 없습니다</div>
			<p class="text-sm text-[var(--color-ink-3)] mt-2">테넌트 네트워크로의 단일 진입점을 생성하세요.</p>
		</div>
	{:else}
		<TableShell>
			<table>
				<thead>
					<tr>
						<th>이름</th>
						<th>상태</th>
						<th>엔드포인트</th>
						<th>터널 CIDR</th>
						<th>피어 수</th>
						<th>생성일</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					{#each servers as server (server.id)}
						<tr class="cursor-pointer" onclick={() => openPanel(server.id)}>
							<td class="text-[var(--color-ink-0)]">{server.name}</td>
							<td><StatusChip status={server.status} /></td>
							<td class="text-[var(--color-ink-2)] text-xs font-mono">{server.endpoint_ip ?? '-'}</td>
							<td class="text-[var(--color-ink-2)] text-xs font-mono">{server.tunnel_cidr}</td>
							<td class="text-[var(--color-ink-2)] text-xs">{server.peer_count ?? '-'}</td>
							<td class="text-[var(--color-ink-2)] text-xs">{formatDate(server.created_at)}</td>
							<td>
								<button
									onclick={(e) => { e.stopPropagation(); deleteServer(server); }}
									class="text-xs text-[var(--color-state-danger)] hover:opacity-80"
								>삭제</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</TableShell>
	{/if}
</div>

{#if selectedServer}
	<SlidePanel onClose={closePanel} width="w-full md:w-[70vw] max-w-3xl" storageKey="slidePanel.vpn-detail.width">
		<div class="p-6">
			<div class="mb-5 flex items-center justify-between">
				<button onclick={closePanel} class="text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)] text-sm transition-colors">✕ 닫기</button>
				<AutoRefreshControl
					bind:active={panelAr.active}
					bind:intervalSeconds={panelAr.intervalSeconds}
					intervalOptions={panelAr.intervalOptions}
					refreshing={clientsLoading}
					onManualRefresh={() => { fetchServers(); if (selectedServerId) fetchClients(selectedServerId); }}
				/>
			</div>

			<div class="flex items-start justify-between mb-6">
				<div>
					<h2 class="text-xl font-semibold text-[var(--color-ink-0)]">{selectedServer.name}</h2>
					<div class="mt-1"><StatusChip status={selectedServer.status} /></div>
				</div>
				<Button onclick={() => deleteServer(selectedServer)} variant="danger-outline" size="sm">서버 삭제</Button>
			</div>

			{#if selectedServer.status_reason}
				<Alert tone="warning" class="mb-4">{selectedServer.status_reason}</Alert>
			{/if}

			<dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm mb-8 bg-[var(--color-surface-raised)] border border-[var(--color-line)] rounded-xl p-4">
				<div>
					<dt class="text-xs text-[var(--color-ink-3)] uppercase tracking-wide">엔드포인트</dt>
					<dd class="text-[var(--color-ink-1)] font-mono">{selectedServer.endpoint_ip ?? '-'}:{selectedServer.listen_port}</dd>
				</div>
				<div>
					<dt class="text-xs text-[var(--color-ink-3)] uppercase tracking-wide">터널 CIDR</dt>
					<dd class="text-[var(--color-ink-1)] font-mono">{selectedServer.tunnel_cidr}</dd>
				</div>
				<div>
					<dt class="text-xs text-[var(--color-ink-3)] uppercase tracking-wide">DNS</dt>
					<dd class="text-[var(--color-ink-1)]">{selectedServer.dns ?? '-'}</dd>
				</div>
				<div>
					<dt class="text-xs text-[var(--color-ink-3)] uppercase tracking-wide">서버 공개키</dt>
					<dd class="text-[var(--color-ink-1)] font-mono text-xs break-all">{selectedServer.server_public_key ?? '(에이전트 등록 대기 중)'}</dd>
				</div>
				<div>
					<dt class="text-xs text-[var(--color-ink-3)] uppercase tracking-wide">마지막 상태 보고</dt>
					<dd class="text-[var(--color-ink-1)]">{formatDate(selectedServer.last_status_reported_at)}</dd>
				</div>
				<div>
					<dt class="text-xs text-[var(--color-ink-3)] uppercase tracking-wide">피어 수</dt>
					<dd class="text-[var(--color-ink-1)]">{selectedServer.peer_count ?? '-'}</dd>
				</div>
			</dl>

			<div class="flex items-center justify-between mb-3">
				<h3 class="text-sm font-medium text-[var(--color-ink-1)]">클라이언트</h3>
				<Button
					onclick={() => { showClientModal = true; clientCreateError = ''; }}
					variant="accent"
					size="sm"
					disabled={selectedServer.status !== 'ACTIVE'}
					title={selectedServer.status !== 'ACTIVE' ? 'VPN 서버가 ACTIVE 상태여야 클라이언트를 발급할 수 있습니다' : undefined}
				>+ 클라이언트 발급</Button>
			</div>

			{#if clientsError}
				<Alert tone="danger" class="mb-4">{clientsError}</Alert>
			{/if}

			{#if clientsLoading && clients.length === 0}
				<LoadingSkeleton variant="table" rows={3} />
			{:else if clients.length === 0}
				<div class="text-center py-10 text-[var(--color-ink-3)] bg-[var(--color-surface-raised)] border border-[var(--color-line)] rounded-xl">
					<div class="text-sm">발급된 클라이언트가 없습니다</div>
				</div>
			{:else}
				<TableShell>
					<table>
						<thead>
							<tr>
								<th>이름</th>
								<th>터널 IP</th>
								<th>상태</th>
								<th>마지막 핸드셰이크</th>
								<th>생성일</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							{#each clients as client (client.id)}
								<tr>
									<td class="text-[var(--color-ink-0)]">{client.name}</td>
									<td class="text-[var(--color-ink-2)] text-xs font-mono">{client.tunnel_ip}</td>
									<td><StatusChip status={clientStatusLabel(client)} /></td>
									<td class="text-[var(--color-ink-2)] text-xs">{formatDate(client.last_handshake_at)}</td>
									<td class="text-[var(--color-ink-2)] text-xs">{formatDate(client.created_at)}</td>
									<td>
										<div class="flex gap-2 justify-end">
											<button
												onclick={() => downloadConfig(client)}
												disabled={downloadingClientId === client.id}
												class="text-xs text-[var(--color-accent)] hover:opacity-80 disabled:opacity-50"
											>{downloadingClientId === client.id ? '다운로드 중...' : '.conf 다운로드'}</button>
											<button onclick={() => toggleClient(client)} class="text-xs text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)]">
												{client.enabled ? '비활성화' : '활성화'}
											</button>
											<button onclick={() => deleteClient(client)} class="text-xs text-[var(--color-state-danger)] hover:opacity-80">삭제</button>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</TableShell>
			{/if}

			<p class="text-xs text-[var(--color-ink-3)] mt-4">
				QR 코드를 통한 모바일 클라이언트 등록은 후속 작업으로 예정되어 있습니다. 현재는 <code>.conf</code> 파일 다운로드만 지원합니다.
			</p>
		</div>
	</SlidePanel>
{/if}

<FormModal
	bind:open={showClientModal}
	title="VPN 클라이언트 발급"
	submitLabel="발급"
	submitting={clientCreating}
	onSubmit={createClient}
	onClose={() => { showClientModal = false; clientCreateError = ''; }}
>
	<div class="space-y-4">
		<Field label="이름" required>
			<TextInput bind:value={newClientName} placeholder="my-laptop" />
		</Field>
		{#if clientCreateError}
			<p class="text-sm text-[var(--color-state-danger)]">{clientCreateError}</p>
		{/if}
	</div>
</FormModal>
