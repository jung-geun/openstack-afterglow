import { get } from 'svelte/store';
import { getContext, setContext } from 'svelte';
import { auth } from '$lib/stores/auth';
import { api, ApiError } from '$lib/api/client';
import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';
import type { Instance } from '$lib/types/compute';
import type { FloatingIpDetail, PortInfo, NetworkInfo } from '$lib/types/networks';
import type { SecurityGroup } from '$lib/types/securityGroup';
import type { Volume as VolumeInfo } from '$lib/types/volume';
import type { VolumeAttachment } from '$lib/types/volume';
import type { SecurityGroupRule } from '$lib/types/securityGroup';

export interface Flavor {
	id: string;
	name: string;
	vcpus: number;
	ram: number;
	disk: number;
}

export interface PasswordPrecheck {
	supported: boolean;
	reason: string | null;
	os_admin_user: string | null;
	server_status: string;
}

export interface InstanceDetailStoreOpts {
	instanceId: () => string;
	effectiveProjectId: () => string | undefined;
	adminMode: () => boolean;
	onDelete: () => void;
}

export function createInstanceDetailStore(opts: InstanceDetailStoreOpts) {
	// Domain state
	let instance = $state<Instance | null>(null);
	let floatingIps = $state<FloatingIpDetail[]>([]);
	let interfaces = $state<PortInfo[]>([]);
	let volumes = $state<VolumeAttachment[]>([]);
	let allSecurityGroups = $state<SecurityGroup[]>([]);
	let availableVolumes = $state<VolumeInfo[]>([]);
	let availableNetworks = $state<NetworkInfo[]>([]);
	let ownerDisplay = $state('');
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let deleting = $state(false);
	let actioning = $state<string | null>(null);
	let consoleLog = $state('');
	let logLoading = $state(false);
	let logFull = $state(false);

	// Admin domain state
	let passwordPrecheck = $state<PasswordPrecheck | null>(null);
	let passwordPrecheckLoading = $state(false);
	let resizeFlavors = $state<Flavor[]>([]);
	let resizeLoading = $state(false);
	let resizeError = $state('');
	let migrateHosts = $state<{ name: string; state: string; status: string }[]>([]);
	let migrateLoading = $state(false);
	let migrateError = $state('');

	// Derived
	const fixedIpsList = $derived(instance?.ip_addresses.filter(ip => ip.type === 'fixed') ?? []);
	const floatingIpsList = $derived(instance?.ip_addresses.filter(ip => ip.type === 'floating') ?? []);
	const assignedPortIds = $derived(new Set(floatingIps.filter(f => f.port_id).map(f => f.port_id!)));
	const availableInterfaces = $derived(interfaces.filter(i => !assignedPortIds.has(i.id)));

	// AutoRefresh instances
	const detailPollAr = createAutoRefresh(() => {
		const id = opts.instanceId();
		if (!id || !get(auth).token) return;
		return fetchInstance(id, { silent: true });
	}, {
		storageKey: 'instance-detail',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60, 120],
	});

	const consolePollAr = createAutoRefresh(() => loadConsoleLog(logFull), {
		storageKey: 'instance-detail-console',
		defaultActive: false,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	// Token/projectId helpers (read at call time — not reactive)
	function tok() { return get(auth).token ?? undefined; }
	function ownPid() { return get(auth).projectId ?? undefined; }

	// Utility functions
	function sgNameById(id: string): string {
		return allSecurityGroups.find(sg => sg.id === id)?.name ?? id.slice(0, 8) + '...';
	}

	function networkNameById(id: string): string {
		return availableNetworks.find(n => n.id === id)?.name ?? id.slice(0, 12) + '...';
	}

	function formatDate(dt: string | null): string {
		if (!dt) return '-';
		return new Date(dt).toLocaleString('ko-KR');
	}

	function formatRule(r: SecurityGroupRule): string {
		const dir = r.direction === 'ingress' ? '인바운드' : '아웃바운드';
		if (!r.protocol) return `${dir} 전체 허용`;
		const proto = r.protocol.toUpperCase();
		let port = '';
		if (r.port_range_min != null && r.port_range_max != null) {
			port = r.port_range_min === r.port_range_max
				? ` ${r.port_range_min}` : ` ${r.port_range_min}-${r.port_range_max}`;
		}
		const remote = r.remote_ip_prefix ? ` ← ${r.remote_ip_prefix}` : '';
		return `${dir} ${proto}${port}${remote}`;
	}

	// Core fetch
	async function fetchInstance(id: string, fetchOpts?: { silent?: boolean }) {
		if (fetchOpts?.silent) {
			refreshing = true;
		} else {
			loading = true;
			error = '';
		}
		const projectId = opts.effectiveProjectId();
		try {
			instance = await api.get<Instance>(`/api/instances/${id}`, tok(), projectId);
			const [fips, ifaces, vols, sgData, allVols, nets, ownerData] = await Promise.all([
				api.get<FloatingIpDetail[]>('/api/networks/floating-ips', tok(), projectId).catch(() => []),
				api.get<PortInfo[]>(`/api/instances/${id}/interfaces`, tok(), projectId).catch(() => []),
				api.get<VolumeAttachment[]>(`/api/instances/${id}/volumes`, tok(), projectId).catch(() => []),
				api.get<{ ports: PortInfo[]; security_groups: SecurityGroup[] }>(`/api/instances/${id}/security-groups`, tok(), projectId).catch(() => ({ ports: [], security_groups: [] })),
				api.get<VolumeInfo[]>('/api/volumes', tok(), projectId).catch(() => []),
				api.get<NetworkInfo[]>('/api/networks', tok(), projectId).catch(() => []),
				api.get<{ display: string }>(`/api/instances/${id}/owner`, tok(), projectId).catch(() => ({ display: '' })),
			]);
			const instIps = new Set(instance.ip_addresses.filter(ip => ip.type === 'floating').map(ip => ip.addr));
			floatingIps = fips.filter(f => instIps.has(f.floating_ip_address));
			interfaces = ifaces;
			volumes = vols;
			allSecurityGroups = sgData.security_groups;
			const attachedIds = new Set(vols.map(v => v.volume_id));
			availableVolumes = allVols.filter(v => v.status === 'available' && !attachedIds.has(v.id));
			availableNetworks = nets;
			ownerDisplay = ownerData.display || '';
			if (opts.adminMode()) fetchPasswordPrecheck(id);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			if (fetchOpts?.silent) refreshing = false;
			else loading = false;
		}
	}

	function manualRefresh() {
		const id = opts.instanceId();
		if (id) fetchInstance(id, { silent: true });
	}

	async function loadConsoleLog(full = false) {
		if (!instance) return;
		logLoading = true;
		const length = full ? 0 : 200;
		try {
			const data = await api.get<{ output: string }>(
				`/api/instances/${instance.id}/log?length=${length}`,
				tok(),
				ownPid()
			);
			consoleLog = data.output || '(로그 없음)';
		} catch {
			consoleLog = '로그를 가져올 수 없습니다';
		} finally {
			logLoading = false;
		}
	}

	async function toggleFullLog() {
		logFull = !logFull;
		await loadConsoleLog(logFull);
	}

	async function openConsole() {
		if (!instance) return;
		try {
			const data = await api.get<{ url: string }>(`/api/instances/${instance.id}/console`, tok(), ownPid());
			window.open(data.url, '_blank');
		} catch {
			toast.error('콘솔 URL을 가져올 수 없습니다');
		}
	}

	async function performAction(action: 'start' | 'stop' | 'reboot' | 'shelve' | 'unshelve') {
		if (!instance) return;
		const labels: Record<string, string> = { start: '시작', stop: '정지', reboot: '재부팅', shelve: '보관', unshelve: '보관 해제' };
		if (!(await confirmDialog(`인스턴스를 ${labels[action]}하시겠습니까?`))) return;
		actioning = action;
		try {
			await api.post(`/api/instances/${instance.id}/${action}`, {}, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error(`${labels[action]} 실패: ` + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function deleteInstance() {
		if (!instance) return;
		const autoDeleteVols = volumes.filter(v => v.delete_on_termination);
		const keepVols = volumes.filter(v => !v.delete_on_termination);
		const lines = [`"${instance.name}" 인스턴스를 삭제하시겠습니까?`];
		if (autoDeleteVols.length) lines.push(`자동 삭제 볼륨: ${autoDeleteVols.map(v => v.name || v.device).join(', ')}`);
		if (keepVols.length) lines.push(`유지(분리만): ${keepVols.map(v => v.name || v.device).join(', ')}`);
		if (instance.union_upper_volume_id) lines.push('Upper 볼륨과 파일 스토리지(dynamic)도 삭제됩니다.');
		if (!(await confirmDialog(lines.join('\n')))) return;
		deleting = true;
		try {
			await api.delete(`/api/instances/${instance.id}`, tok(), ownPid());
			opts.onDelete();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}

	async function assignFloatingIp(portId: string) {
		if (!instance) return;
		actioning = 'fip-assign-' + portId;
		try {
			await api.post(`/api/instances/${instance.id}/floating-ip?port_id=${portId}`, {}, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('Floating IP 할당 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function releaseFloatingIp(fipId: string) {
		if (!instance) return;
		if (!(await confirmDialog('Floating IP를 해제하고 삭제하시겠습니까?'))) return;
		actioning = 'fip-release-' + fipId;
		try {
			await api.post(`/api/networks/floating-ips/${fipId}/disassociate`, {}, tok(), ownPid());
			await api.delete(`/api/networks/floating-ips/${fipId}`, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('Floating IP 해제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function attachVolume(volumeId: string) {
		if (!instance) return;
		actioning = 'attach-vol';
		try {
			await api.post(`/api/instances/${instance.id}/volumes`, { volume_id: volumeId }, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('볼륨 연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function createAndAttachVolume(name: string, sizeGb: number) {
		if (!instance) return;
		actioning = 'create-vol';
		try {
			const vol = await api.post<VolumeInfo>('/api/volumes', { name, size_gb: sizeGb }, tok(), ownPid());
			await api.post(`/api/instances/${instance.id}/volumes`, { volume_id: vol.id }, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('볼륨 생성/연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function detachVolume(volumeId: string) {
		if (!instance) return;
		if (!(await confirmDialog('볼륨을 분리하시겠습니까?'))) return;
		actioning = 'detach-' + volumeId;
		try {
			await api.delete(`/api/instances/${instance.id}/volumes/${volumeId}`, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('볼륨 분리 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function setDeleteOnTermination(volumeId: string, next: boolean) {
		if (!instance) return;
		const verb = next ? '활성화' : '비활성화';
		if (!(await confirmDialog(`이 볼륨의 "인스턴스 삭제 시 자동 삭제" 옵션을 ${verb}하시겠습니까?`))) return;
		actioning = 'dot-' + volumeId;
		try {
			await api.patch(`/api/instances/${instance.id}/volumes/${volumeId}`, { delete_on_termination: next }, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('변경 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function attachInterface(netId: string) {
		if (!instance) return;
		actioning = 'attach-iface';
		try {
			await api.post(`/api/instances/${instance.id}/interfaces`, { net_id: netId }, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('인터페이스 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function detachInterface(portId: string) {
		if (!instance) return;
		if (!(await confirmDialog('인터페이스를 제거하시겠습니까?'))) return;
		actioning = 'detach-iface-' + portId;
		try {
			await api.delete(`/api/instances/${instance.id}/interfaces/${portId}`, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('인터페이스 제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function saveSgEdit(portId: string, sgIds: string[]) {
		if (!instance) return;
		actioning = 'sg-' + portId;
		try {
			await api.post(
				`/api/instances/${instance.id}/ports/${portId}/security-groups`,
				{ security_group_ids: sgIds },
				tok(),
				ownPid()
			);
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('보안 그룹 업데이트 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	// Admin: resize
	async function loadResizeFlavors() {
		resizeFlavors = [];
		resizeError = '';
		try {
			resizeFlavors = await api.get<Flavor[]>('/api/flavors', tok(), ownPid());
		} catch {
			resizeFlavors = [];
		}
	}

	async function doResize(flavorId: string): Promise<boolean> {
		if (!instance) return false;
		resizeLoading = true;
		resizeError = '';
		try {
			await api.post(`/api/admin/instances/${instance.id}/resize`, { flavor_id: flavorId }, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
			return true;
		} catch (e) {
			resizeError = e instanceof ApiError ? e.message : '리사이즈 실패';
			return false;
		} finally {
			resizeLoading = false;
		}
	}

	async function revertResize() {
		if (!instance) return;
		if (!(await confirmDialog('리사이즈를 취소하고 이전 플레이버로 복귀하시겠습니까?'))) return;
		actioning = 'revert-resize';
		try {
			await api.post(`/api/admin/instances/${instance.id}/revert-resize`, {}, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('리사이즈 취소 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	async function confirmResize() {
		if (!instance) return;
		if (!(await confirmDialog('리사이즈를 확인하시겠습니까?'))) return;
		actioning = 'confirm-resize';
		try {
			await api.post(`/api/admin/instances/${instance.id}/confirm-resize`, {}, tok(), ownPid());
			await fetchInstance(instance.id, { silent: true });
		} catch (e) {
			toast.error('리사이즈 확인 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			actioning = null;
		}
	}

	// Admin: password precheck
	async function fetchPasswordPrecheck(serverId: string) {
		passwordPrecheckLoading = true;
		try {
			passwordPrecheck = await api.get<PasswordPrecheck>(
				`/api/instances/${serverId}/admin-password/precheck`,
				tok(),
				ownPid()
			);
		} catch {
			passwordPrecheck = null;
		} finally {
			passwordPrecheckLoading = false;
		}
	}

	// Returns error string on failure, null on success
	async function doSetPassword(password: string): Promise<string | null> {
		if (!instance) return '인스턴스 없음';
		try {
			await api.post(`/api/instances/${instance.id}/admin-password`, { new_password: password }, tok(), ownPid());
			return null;
		} catch (e) {
			return e instanceof ApiError ? e.message : '패스워드 변경 실패';
		}
	}

	// Admin: migrate
	async function loadMigrateHosts() {
		migrateHosts = [];
		migrateError = '';
		try {
			migrateHosts = await api.get<{ name: string; state: string; status: string }[]>(
				'/api/admin/compute-hosts',
				tok(),
				ownPid()
			);
		} catch {
			migrateHosts = [];
		}
	}

	async function doMigrate(type: 'live' | 'cold', host: string): Promise<boolean> {
		if (!instance) return false;
		migrateLoading = true;
		migrateError = '';
		try {
			if (type === 'live') {
				await api.post(`/api/admin/instances/${instance.id}/live-migrate`, { host: host || null, block_migration: 'auto' }, tok(), ownPid());
			} else {
				await api.post(`/api/admin/instances/${instance.id}/cold-migrate`, {}, tok(), ownPid());
			}
			await fetchInstance(instance.id, { silent: true });
			return true;
		} catch (e) {
			migrateError = e instanceof ApiError ? e.message : '마이그레이션 실패';
			return false;
		} finally {
			migrateLoading = false;
		}
	}

	return {
		get instance() { return instance; },
		get floatingIps() { return floatingIps; },
		get interfaces() { return interfaces; },
		get volumes() { return volumes; },
		get allSecurityGroups() { return allSecurityGroups; },
		get availableVolumes() { return availableVolumes; },
		get availableNetworks() { return availableNetworks; },
		get ownerDisplay() { return ownerDisplay; },
		get loading() { return loading; },
		get refreshing() { return refreshing; },
		get error() { return error; },
		get deleting() { return deleting; },
		get actioning() { return actioning; },
		get consoleLog() { return consoleLog; },
		get logLoading() { return logLoading; },
		get logFull() { return logFull; },
		set logFull(v: boolean) { logFull = v; },
		get fixedIpsList() { return fixedIpsList; },
		get floatingIpsList() { return floatingIpsList; },
		get assignedPortIds() { return assignedPortIds; },
		get availableInterfaces() { return availableInterfaces; },
		get passwordPrecheck() { return passwordPrecheck; },
		get passwordPrecheckLoading() { return passwordPrecheckLoading; },
		get resizeFlavors() { return resizeFlavors; },
		get resizeLoading() { return resizeLoading; },
		get resizeError() { return resizeError; },
		set resizeError(v: string) { resizeError = v; },
		get migrateHosts() { return migrateHosts; },
		get migrateLoading() { return migrateLoading; },
		get migrateError() { return migrateError; },
		set migrateError(v: string) { migrateError = v; },
		detailPollAr,
		consolePollAr,
		fetchInstance,
		manualRefresh,
		loadConsoleLog,
		toggleFullLog,
		openConsole,
		performAction,
		deleteInstance,
		assignFloatingIp,
		releaseFloatingIp,
		attachVolume,
		createAndAttachVolume,
		detachVolume,
		setDeleteOnTermination,
		attachInterface,
		detachInterface,
		saveSgEdit,
		loadResizeFlavors,
		doResize,
		revertResize,
		confirmResize,
		fetchPasswordPrecheck,
		doSetPassword,
		loadMigrateHosts,
		doMigrate,
		sgNameById,
		networkNameById,
		formatDate,
		formatRule,
	};
}

export type InstanceDetailStore = ReturnType<typeof createInstanceDetailStore>;

const INSTANCE_DETAIL_KEY = Symbol('instance-detail');

export function provideInstanceDetail(store: InstanceDetailStore) {
	setContext(INSTANCE_DETAIL_KEY, store);
}

export function useInstanceDetail(): InstanceDetailStore {
	const store = getContext<InstanceDetailStore | undefined>(INSTANCE_DETAIL_KEY);
	if (!store) throw new Error('useInstanceDetail must be called within InstanceDetailPanel');
	return store;
}
