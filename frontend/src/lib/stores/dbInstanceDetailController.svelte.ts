import { getContext, setContext } from 'svelte';
import { api, ApiError } from '$lib/api/client';
import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';
import type { DbInstance, DbFlavor, DbDatabase, DbUser, DbBackup } from '$lib/types/database';
import type { FloatingIp } from '$lib/types/networks';

export interface DbInstanceDetailControllerOpts {
	instanceId: () => string;
	token: () => string | undefined;
	projectId: () => string | undefined;
	onDeleted?: () => void;
}

export function createDbInstanceDetailController(opts: DbInstanceDetailControllerOpts) {
	// Domain state
	let instance = $state<DbInstance | null>(null);
	let databases = $state<DbDatabase[]>([]);
	let users = $state<DbUser[]>([]);
	let backups = $state<DbBackup[]>([]);
	let flavors = $state<DbFlavor[]>([]);
	let floatingIps = $state<FloatingIp[]>([]);
	let rootInfo = $state<{ name: string; password: string } | null>(null);
	let loading = $state(true);
	let enablingRoot = $state(false);
	let deleting = $state(false);
	let attachingFip = $state(false);
	let detachingFip = $state(false);
	let fipError = $state('');

	// Database sub-resource state
	let creatingDb = $state(false);
	let dbError = $state('');
	let deletingDb = $state<string | null>(null);

	// User sub-resource state
	let creatingUser = $state(false);
	let userError = $state('');
	let deletingUser = $state<string | null>(null);

	// Backup sub-resource state
	let creatingBackup = $state(false);
	let backupError = $state('');
	let deletingBackup = $state<string | null>(null);
	let restoringBackup = $state<string | null>(null);

	// Derived
	const instanceFips = $derived.by(() => {
		const ips = instance?.ips ?? [];
		return floatingIps.filter(f => f.fixed_ip_address && ips.includes(f.fixed_ip_address));
	});
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

	// AutoRefresh
	const ar = createAutoRefresh(() => loadAll(), {
		storageKey: 'dashboard-db-instance-detail',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	// Handlers
	async function loadAll() {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		loading = true;
		await Promise.allSettled([
			api.get<DbInstance>(`/api/database-instances/${id}`, tok, proj)
				.then(v => { instance = v; loading = false; })
				.catch(() => { instance = null; loading = false; }),
			api.get<DbDatabase[]>(`/api/database-instances/${id}/databases`, tok, proj)
				.then(v => { databases = v; })
				.catch(() => {}),
			api.get<DbUser[]>(`/api/database-instances/${id}/users`, tok, proj)
				.then(v => { users = v; })
				.catch(() => {}),
			api.get<DbBackup[]>(`/api/database-instances/${id}/backups`, tok, proj)
				.then(v => { backups = v; })
				.catch(() => {}),
			flavors.length === 0
				? api.get<DbFlavor[]>('/api/database-instances/flavors', tok, proj)
					.then(v => { flavors = v; })
					.catch(() => {})
				: Promise.resolve(),
			api.get<FloatingIp[]>('/api/networks/floating-ips', tok, proj)
				.then(v => { floatingIps = v; })
				.catch(() => {}),
		]);
		loading = false;
	}

	function reset() {
		instance = null;
		databases = [];
		users = [];
		backups = [];
		rootInfo = null;
		loading = true;
	}

	async function attachFip() {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		attachingFip = true; fipError = '';
		try {
			await api.post(`/api/database-instances/${id}/floating-ip`, {}, tok, proj);
			floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', tok, proj);
		} catch (e) { fipError = e instanceof ApiError ? e.message : '실패'; }
		finally { attachingFip = false; }
	}

	async function detachFip(deleteFip: boolean) {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		const verb = deleteFip ? '삭제' : '해제';
		if (!(await confirmDialog(`이 인스턴스의 floating IP를 ${verb}하시겠습니까?`))) return;
		detachingFip = true; fipError = '';
		try {
			await api.delete(
				`/api/database-instances/${id}/floating-ip${deleteFip ? '?delete=true' : ''}`,
				tok, proj
			);
			floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', tok, proj);
		} catch (e) { fipError = e instanceof ApiError ? e.message : '실패'; }
		finally { detachingFip = false; }
	}

	async function deleteInstance() {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		if (!(await confirmDialog(`DB 인스턴스 "${instance?.name}"를 삭제하시겠습니까?`))) return;
		deleting = true;
		try {
			await api.delete(`/api/database-instances/${id}`, tok, proj);
			opts.onDeleted?.();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			deleting = false;
		}
	}

	async function enableRoot() {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		enablingRoot = true;
		try {
			rootInfo = await api.post<{ name: string; password: string }>(
				`/api/database-instances/${id}/root`, {}, tok, proj
			);
		} catch (e) {
			toast.error('root 활성화 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			enablingRoot = false;
		}
	}

	async function createDb(name: string) {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		creatingDb = true; dbError = '';
		try {
			const isMysqlLike = dsType.match(/^(mysql|mariadb|percona)/i);
			const payload = isMysqlLike
				? { name, character_set: 'utf8mb4', collate: 'utf8mb4_unicode_ci' }
				: { name };
			await api.post(`/api/database-instances/${id}/databases`, payload, tok, proj);
			databases = await api.get<DbDatabase[]>(`/api/database-instances/${id}/databases`, tok, proj);
			return true;
		} catch (e) { dbError = e instanceof ApiError ? e.message : '실패'; return false; }
		finally { creatingDb = false; }
	}

	async function deleteDb(name: string) {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		if (!(await confirmDialog(`데이터베이스 "${name}"를 삭제하시겠습니까?`))) return;
		deletingDb = name;
		try {
			await api.delete(`/api/database-instances/${id}/databases/${encodeURIComponent(name)}`, tok, proj);
			databases = databases.filter(d => d.name !== name);
		} catch (e) { toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { deletingDb = null; }
	}

	async function createUser(newUser: { name: string; password: string; host: string; dbNames: string[] }) {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		creatingUser = true; userError = '';
		try {
			await api.post(`/api/database-instances/${id}/users`, {
				name: newUser.name,
				password: newUser.password,
				host: newUser.host || '%',
				databases: newUser.dbNames,
			}, tok, proj);
			users = await api.get<DbUser[]>(`/api/database-instances/${id}/users`, tok, proj);
			return true;
		} catch (e) { userError = e instanceof ApiError ? e.message : '실패'; return false; }
		finally { creatingUser = false; }
	}

	async function deleteUser(u: DbUser) {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		const host = u.host || '%';
		const label = host !== '%' ? `${u.name}@${host}` : u.name;
		if (!(await confirmDialog(`유저 "${label}"를 삭제하시겠습니까?`))) return;
		deletingUser = label;
		try {
			const url = `/api/database-instances/${id}/users/${encodeURIComponent(u.name)}`
				+ `?host=${encodeURIComponent(host)}`;
			await api.delete(url, tok, proj);
			users = users.filter(x => !(x.name === u.name && x.host === u.host));
		} catch (e) { toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { deletingUser = null; }
	}

	async function createBackup(name: string, description: string) {
		const id = opts.instanceId();
		const tok = opts.token();
		const proj = opts.projectId();
		creatingBackup = true; backupError = '';
		try {
			await api.post(`/api/database-instances/${id}/backups`, { name, description }, tok, proj);
			backups = await api.get<DbBackup[]>(`/api/database-instances/${id}/backups`, tok, proj);
			return true;
		} catch (e) { backupError = e instanceof ApiError ? e.message : '실패'; return false; }
		finally { creatingBackup = false; }
	}

	async function deleteBackup(backupId: string) {
		if (!(await confirmDialog('백업을 삭제하시겠습니까?'))) return;
		const tok = opts.token();
		const proj = opts.projectId();
		deletingBackup = backupId;
		try {
			await api.delete(`/api/database-instances/backups/${backupId}`, tok, proj);
			backups = backups.filter(b => b.id !== backupId);
		} catch (e) { toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { deletingBackup = null; }
	}

	async function restoreBackup(backupId: string) {
		const tok = opts.token();
		const proj = opts.projectId();
		const name = prompt('복원할 새 인스턴스 이름을 입력하세요:');
		if (!name) return;
		restoringBackup = backupId;
		try {
			await api.post('/api/database-instances/restore', {
				backup_id: backupId, name,
				flavor_id: instance?.flavor_id ?? '',
				volume_size: instance?.size ?? 5,
			}, tok, proj);
			toast.success('복원 인스턴스 생성이 시작되었습니다.');
			opts.onDeleted?.();
		} catch (e) { toast.error('복원 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { restoringBackup = null; }
	}

	return {
		// AutoRefresh (직접 바인딩용)
		get ar() { return ar; },

		// State getters
		get instance() { return instance; },
		get databases() { return databases; },
		get users() { return users; },
		get backups() { return backups; },
		get flavors() { return flavors; },
		get floatingIps() { return floatingIps; },
		get rootInfo() { return rootInfo; },
		get loading() { return loading; },
		get enablingRoot() { return enablingRoot; },
		get deleting() { return deleting; },
		get attachingFip() { return attachingFip; },
		get detachingFip() { return detachingFip; },
		get fipError() { return fipError; },
		get creatingDb() { return creatingDb; },
		get dbError() { return dbError; },
		get deletingDb() { return deletingDb; },
		get creatingUser() { return creatingUser; },
		get userError() { return userError; },
		get deletingUser() { return deletingUser; },
		get creatingBackup() { return creatingBackup; },
		get backupError() { return backupError; },
		get deletingBackup() { return deletingBackup; },
		get restoringBackup() { return restoringBackup; },

		// Derived getters
		get instanceFips() { return instanceFips; },
		get dsType() { return dsType; },
		get flavorDisplay() { return flavorDisplay; },
		get dbPort() { return dbPort; },
		get connectHost() { return connectHost; },
		get connectCmd() { return connectCmd; },

		// Setters (서브 컴포넌트에서 에러 초기화용)
		set dbError(v: string) { dbError = v; },
		set userError(v: string) { userError = v; },
		set backupError(v: string) { backupError = v; },

		// Handlers
		loadAll,
		reset,
		attachFip,
		detachFip,
		deleteInstance,
		enableRoot,
		createDb,
		deleteDb,
		createUser,
		deleteUser,
		createBackup,
		deleteBackup,
		restoreBackup,
	};
}

export type DbInstanceDetailController = ReturnType<typeof createDbInstanceDetailController>;

const DB_INSTANCE_DETAIL_KEY = Symbol('db-instance-detail');

export function provideDbInstanceDetailController(store: DbInstanceDetailController) {
	setContext(DB_INSTANCE_DETAIL_KEY, store);
}

export function useDbInstanceDetailController(): DbInstanceDetailController {
	const store = getContext<DbInstanceDetailController | undefined>(DB_INSTANCE_DETAIL_KEY);
	if (!store) throw new Error('useDbInstanceDetailController must be called within DbInstanceDetailPanel');
	return store;
}
