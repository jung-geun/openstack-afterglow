import { get } from 'svelte/store';
import { goto } from '$app/navigation';
import { setContext, getContext } from 'svelte';
import { wizard, resetWizard, closeWizard } from '$lib/stores/wizard';
import { api, ApiError, getBaseUrl } from '$lib/api/client';
import { auth } from '$lib/stores/auth';
import { betaFeatures } from '$lib/stores/betaFeatures';
import type { BetaFeatures } from '$lib/stores/betaFeatures';
import { toast } from '$lib/stores/toast';
import type { NetworkInfo } from '$lib/types/networks';
import type { SecurityGroup as SecurityGroupInfo } from '$lib/types/securityGroup';
import type { Volume } from '$lib/types/volume';
import type { KeypairInfo } from '$lib/types/keypair';
import type { AvailabilityZone as AvailabilityZoneInfo } from '$lib/types/compute';

interface ProgressMessage {
	step: string;
	progress: number;
	message: string;
	instance_id?: string;
	error?: string;
	elapsed_seconds?: number | null;
}

interface ProjectInfo { id: string; name: string; }
interface QuotaPair { used: number; quota: number; }
interface ProjectQuota {
	project_id: string;
	project_name: string;
	cpu: QuotaPair;
	ram_mb: QuotaPair;
	instances: QuotaPair;
	disk_gb: QuotaPair;
	gpu_instances?: number;
}
interface VmImage {
	id: string;
	name?: string;
	os_distro?: string | null;
	os_version?: string | null;
	properties?: Record<string, unknown> | null;
}
interface VmFlavor {
	id: string;
	name?: string;
	vcpus: number;
	ram: number;
	disk: number;
	extra_specs?: Record<string, string>;
}
interface LibraryItem {
	id: string;
	name: string;
	version: string;
	depends_on: string[];
	available_prebuilt: boolean;
	share_proto: string;
	size_bytes?: number;
}
interface QuotaBlock {
	instances?: { limit: number; in_use: number };
	cores?: { limit: number; in_use: number };
	ram?: { limit: number; in_use: number };
	gigabytes?: { limit: number; in_use: number };
}
interface QuotaResponse { compute?: QuotaBlock; storage?: QuotaBlock; volume?: QuotaBlock; }
export interface FlavorQuotaSummary {
	instances?: { limit: number; in_use: number };
	cores?: { limit: number; in_use: number };
	ram?: { limit: number; in_use: number };
	gigabytes?: { limit: number; in_use: number };
}

export interface SquashfsArtifact {
	id: number;
	name: string;
	parent_id: number | null;
	ubuntu_base?: string | null;
	base_image_id?: string | null;
	base_image_name?: string | null;
}

export interface SquashfsProfile {
	id: number;
	name: string;
	layers: string[];
	artifacts?: SquashfsArtifact[];
	base_image?: {
		ubuntu_base?: string | null;
		base_image_id?: string | null;
		base_image_name?: string | null;
	};
}

export function detectUbuntuBaseImage(
	image: Pick<VmImage, 'name' | 'os_distro' | 'os_version' | 'properties'> | null | undefined,
	fallbackName?: string | null,
): string | null {
	if (!image) return null;
	const props = image.properties ?? {};
	const distro = String(image.os_distro ?? props.os_distro ?? '').toLowerCase();
	const version = String(image.os_version ?? props.os_version ?? props.os_version_id ?? props.release ?? '');
	const versionMatch = version.match(/^(18\.04|20\.04|22\.04|24\.04)/);
	if (distro === 'ubuntu' && versionMatch) return versionMatch[1];
	const name = image.name ?? fallbackName ?? '';
	const nameMatch = name.match(/ubuntu[^0-9]*(18\.04|20\.04|22\.04|24\.04)/i);
	return nameMatch ? nameMatch[1] : null;
}

export function normalizeSchedulingForBeta(
	beta: Pick<BetaFeatures, 'haDeploy'>,
	scheduling: 'standard' | 'ha',
): 'standard' | 'ha' {
	return beta.haDeploy ? scheduling : 'standard';
}

export function isSquashfsWizardEligible(options: {
	beta: Pick<BetaFeatures, 'libraryConsume'>;
	adminMode: boolean;
	bootSource: 'image' | 'volume';
	selectedImageUbuntuBase: string | null;
}): boolean {
	return !options.adminMode && options.beta.libraryConsume && options.bootSource === 'image' && Boolean(options.selectedImageUbuntuBase);
}

export function isSquashfsSelectionReady(options: {
	squashfsMode: 'profile' | 'artifacts' | null;
	layerProfileName: string | null;
	layerArtifactIds: number[];
	squashfsBaseMismatch: boolean;
}): boolean {
	if (options.squashfsMode === 'profile') return Boolean(options.layerProfileName) && !options.squashfsBaseMismatch;
	if (options.squashfsMode === 'artifacts') return options.layerArtifactIds.length > 0 && !options.squashfsBaseMismatch;
	return true;
}

export function shouldUseSquashfsConsume(options: {
	beta: Pick<BetaFeatures, 'libraryConsume'>;
	adminMode: boolean;
	bootSource: 'image' | 'volume';
	selectedImageUbuntuBase: string | null;
	squashfsMode: 'profile' | 'artifacts' | null;
	layerProfileName: string | null;
	layerArtifactIds: number[];
	squashfsBaseMismatch: boolean;
}): boolean {
	if (
		!isSquashfsWizardEligible({
			beta: options.beta,
			adminMode: options.adminMode,
			bootSource: options.bootSource,
			selectedImageUbuntuBase: options.selectedImageUbuntuBase,
		})
	) {
		return false;
	}
	return isSquashfsSelectionReady({
		squashfsMode: options.squashfsMode,
		layerProfileName: options.layerProfileName,
		layerArtifactIds: options.layerArtifactIds,
		squashfsBaseMismatch: options.squashfsBaseMismatch,
	}) && options.squashfsMode !== null;
}

export const TOTAL_STEPS = 6;
export const STEP_LABELS = ['이미지', '플레이버', '라이브러리', '전략', '설정', '배포'];

export const ALL_PROGRESS_STEPS = [
	{ id: 'manila_preparing', label: 'File Storage', description: '파일 스토리지 준비', needsLibrary: true },
	{ id: 'boot_volume_creating', label: '부트 볼륨', description: 'OS 이미지 볼륨 생성', needsLibrary: false },
	{ id: 'upper_volume_creating', label: 'Upper 볼륨', description: 'OverlayFS upperdir 생성', needsLibrary: true },
	{ id: 'userdata_generating', label: 'cloud-init', description: '초기화 스크립트 생성', needsLibrary: true },
	{ id: 'server_creating', label: 'VM 생성', description: 'Nova 인스턴스 생성', needsLibrary: false },
	{ id: 'attaching_volume', label: '볼륨 연결', description: '추가 볼륨 연결', needsLibrary: false },
	{ id: 'floating_ip_creating', label: 'Floating IP', description: 'Floating IP 할당', needsLibrary: false },
	{ id: 'completed', label: '완료', description: '배포 완료', needsLibrary: false },
	{ id: 'failed', label: '실패', description: '배포 실패', needsLibrary: false },
];

interface VmCreateOpts {
	adminMode: () => boolean;
}

export type VmCreateStore = ReturnType<typeof createVmCreateStore>;

const VM_CREATE_KEY = Symbol('vm-create');
export function provideVmCreate(store: VmCreateStore) { setContext(VM_CREATE_KEY, store); }
export function useVmCreate(): VmCreateStore {
	const s = getContext<VmCreateStore>(VM_CREATE_KEY);
	if (!s) throw new Error('useVmCreate must be called within VmCreatePanel');
	return s;
}

export function createVmCreateStore(opts: VmCreateOpts) {
	// Mirror writable stores in runes for reactive derived values
	let wizardState = $state(get(wizard));
	let betaState = $state(get(betaFeatures));
	$effect(() => wizard.subscribe(v => { wizardState = v; }));
	$effect(() => betaFeatures.subscribe(v => { betaState = v; }));
	let images = $state<VmImage[]>([]);
	let flavors = $state<VmFlavor[]>([]);
	let libraries = $state<LibraryItem[]>([]);
	let networks = $state<NetworkInfo[]>([]);
	let keypairs = $state<KeypairInfo[]>([]);
	let volumes = $state<Volume[]>([]);
	let fileStorages = $state<{ id: string; name: string; status: string; share_proto: string }[]>([]);
	let securityGroups = $state<SecurityGroupInfo[]>([]);
	let availabilityZones = $state<AvailabilityZoneInfo[]>([]);
	let defaultNetworkId = $state<string | null>(null);
	let squashfsProfiles = $state<SquashfsProfile[]>([]);
	let squashfsArtifacts = $state<SquashfsArtifact[]>([]);
	let flavorQuota = $state<FlavorQuotaSummary | null>(null);

	// UI state
	let loading = $state(false);
	let loadError = $state('');
	let deploying = $state(false);
	let deployError = $state('');
	let currentStep = $state('manila_preparing');
	let progress = $state(0);
	let progressMessage = $state('');
	let elapsedSeconds = $state<number | null>(null);

	// Admin state
	let adminProjects = $state<ProjectInfo[]>([]);
	let adminProjectsLoading = $state(false);
	let adminProjectQuotas = $state<Map<string, ProjectQuota>>(new Map());
	let adminProjectSearch = $state('');
	let adminSelectedProjectId = $state<string | null>(null);
	let adminSelectedProjectName = $state<string | null>(null);

	// Derived
	const filteredAdminProjects = $derived.by(() => {
		const q = adminProjectSearch.trim().toLowerCase();
		if (!q) return adminProjects;
		return adminProjects.filter(p =>
			p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)
		);
	});

	const progressSteps = $derived(
		wizardState.libraries.length > 0
			? ALL_PROGRESS_STEPS
			: ALL_PROGRESS_STEPS.filter(s => !s.needsLibrary)
	);

	const ubuntuVersion = $derived.by(() => {
		const name = wizardState.imageName ?? '';
		const m = name.match(/(\d{2}\.\d{2})/);
		return m ? m[1] : undefined;
	});

	const selectedImage = $derived.by(() => (
		wizardState.imageId ? images.find(image => image.id === wizardState.imageId) ?? null : null
	));

	const selectedImageUbuntuBase = $derived.by(() => detectUbuntuBaseImage(selectedImage, wizardState.imageName));

	const selectedSquashfsArtifacts = $derived(
		squashfsArtifacts.filter(artifact => wizardState.layerArtifactIds.includes(artifact.id))
	);

	const squashfsEligible = $derived.by(() =>
		isSquashfsWizardEligible({
			beta: betaState,
			adminMode: opts.adminMode(),
			bootSource: wizardState.bootSource,
			selectedImageUbuntuBase,
		})
	);

	const squashfsBaseMismatch = $derived.by(() => {
		if (!wizardState.squashfsMode || !wizardState.imageId) return false;
		const selectedBaseIds = new Set(selectedSquashfsArtifacts.map(a => a.base_image_id).filter(Boolean));
		if (wizardState.squashfsMode === 'profile' && wizardState.layerProfileName) {
			const profile = squashfsProfiles.find(p => p.name === wizardState.layerProfileName);
			const profileBaseId = profile?.base_image?.base_image_id;
			return Boolean(profileBaseId && profileBaseId !== wizardState.imageId);
		}
		return selectedBaseIds.size > 0 && (selectedBaseIds.size !== 1 || !selectedBaseIds.has(wizardState.imageId));
	});

	const squashfsSelectionReady = $derived.by(() =>
		isSquashfsSelectionReady({
			squashfsMode: wizardState.squashfsMode,
			layerProfileName: wizardState.layerProfileName,
			layerArtifactIds: wizardState.layerArtifactIds,
			squashfsBaseMismatch,
		})
	);

	const selectedNetwork = $derived(
		wizardState.networkId ? networks.find(n => n.id === wizardState.networkId) ?? null : null
	);

	const hasGpuFlavor = $derived(
		flavors.find(f => f.id === wizardState.flavorId)
			? Object.keys(flavors.find(f => f.id === wizardState.flavorId)?.extra_specs ?? {}).some(
				k => k.toLowerCase().includes('gpu') || k.startsWith('pci_passthrough')
			)
			: false
	);

	const hasPrebuilt = $derived(
		libraries.some(l => wizardState.libraries.includes(l.id) && l.available_prebuilt)
	);

	const selectedFlavorDetail = $derived.by(() => {
		const f = flavors.find(fl => fl.id === wizardState.flavorId);
		if (!f) return '';
		const parts = [
			`${f.vcpus} vCPU`,
			`${f.ram >= 1024 ? Math.round(f.ram / 1024) + ' GB' : f.ram + ' MB'}`,
			`${f.disk} GB`,
		];
		const alias = f.extra_specs?.['pci_passthrough:alias'] ?? '';
		if (alias) {
			const gpuParts = alias.split(',').filter((e: string) => e.includes(':') && !e.toLowerCase().includes('audio'));
			gpuParts.forEach((e: string) => {
				const idx = e.lastIndexOf(':');
				const model = e.slice(0, idx).trim();
				const count = parseInt(e.slice(idx + 1)) || 1;
				parts.push(`${model} ${count > 1 ? '× ' + count : ''}`);
			});
		}
		return parts.join(' · ');
	});

	$effect(() => {
		const needsSchedulingReset = wizardState.scheduling !== normalizeSchedulingForBeta(betaState, wizardState.scheduling);
		const needsSquashfsReset = !squashfsEligible && wizardState.squashfsMode !== null;
		if (!needsSchedulingReset && !needsSquashfsReset) return;
		wizard.update(w => {
			let next = w;
			const nextScheduling = normalizeSchedulingForBeta(betaState, next.scheduling);
			if (nextScheduling !== next.scheduling) {
				next = { ...next, scheduling: nextScheduling };
			}
			if (!squashfsEligible && next.squashfsMode !== null) {
				next = { ...next, squashfsMode: null, layerProfileName: null, layerArtifactIds: [] };
			}
			return next;
		});
	});

	const canNext = $derived((() => {
		const adminMode = opts.adminMode();
		switch (wizardState.step) {
			case 1: return wizardState.bootSource === 'volume' ? !!wizardState.bootVolumeId : !!wizardState.imageId;
			case 2: return !!wizardState.flavorId;
			case 3: return squashfsSelectionReady;
			case 4: {
				if (!wizardState.scheduling) return false;
				if (wizardState.libraries.length > 0 && !wizardState.strategy) return false;
				return true;
			}
			case 5: return !!wizardState.instanceName.trim() && (adminMode || !!wizardState.keyName);
			case 6: return !!wizardState.instanceName.trim();
			default: return false;
		}
	})());

	const needsProjectSelect = $derived(opts.adminMode() && !adminSelectedProjectId);

	// Helpers
	function fmtRemaining(p?: QuotaPair): string {
		if (!p) return '-';
		if (p.quota < 0) return '∞';
		return String(Math.max(0, p.quota - p.used));
	}

	function isExhausted(p?: QuotaPair): boolean {
		if (!p || p.quota < 0) return false;
		return p.used >= p.quota;
	}

	function resolveAllDeps(id: string): string[] {
		const result: string[] = [];
		const visited = new Set<string>();
		function visit(lid: string) {
			if (visited.has(lid)) return;
			visited.add(lid);
			const lib = libraries.find(l => l.id === lid);
			if (lib) (lib.depends_on ?? []).forEach(d => visit(d));
			result.push(lid);
		}
		visit(id);
		return result;
	}

	function lineageIdsForArtifact(id: number): number[] {
		const byId = new Map(squashfsArtifacts.map(artifact => [artifact.id, artifact]));
		const chain: number[] = [];
		const seen = new Set<number>();
		let current = byId.get(id);
		while (current && !seen.has(current.id)) {
			seen.add(current.id);
			chain.unshift(current.id);
			current = current.parent_id ? byId.get(current.parent_id) : undefined;
		}
		return chain;
	}

	async function loadSquashfsCatalog() {
		const token = get(auth).token ?? undefined;
		const projectId = get(auth).projectId ?? undefined;
		try {
			[squashfsProfiles, squashfsArtifacts] = await Promise.all([
				api.get<SquashfsProfile[]>('/api/v1/libraries/squashfs/profiles', token, projectId),
				api.get<SquashfsArtifact[]>('/api/v1/libraries/squashfs/artifacts', token, projectId),
			]);
		} catch {
			squashfsProfiles = [];
			squashfsArtifacts = [];
		}
	}

	// Data loading
	async function loadFlavorQuota() {
		const token = get(auth).token ?? undefined;
		const projectId = get(auth).projectId ?? undefined;
		try {
			if (opts.adminMode() && adminSelectedProjectId) {
				const r = await api.get<QuotaResponse>(
					`/api/v1/admin/quotas/${encodeURIComponent(adminSelectedProjectId)}`, token, projectId,
				);
				flavorQuota = {
					instances: r.compute?.instances,
					cores: r.compute?.cores,
					ram: r.compute?.ram,
					gigabytes: r.volume?.gigabytes,
				};
			} else if (!opts.adminMode()) {
				const r = await api.get<QuotaResponse>('/api/v1/dashboard/quotas', token, projectId);
				flavorQuota = {
					instances: r.compute?.instances,
					cores: r.compute?.cores,
					ram: r.compute?.ram,
					gigabytes: r.storage?.gigabytes,
				};
			}
		} catch {
			flavorQuota = null;
		}
	}

	async function loadAdminProjectQuotas() {
		if (!opts.adminMode()) return;
		const token = get(auth).token ?? undefined;
		const projectId = get(auth).projectId ?? undefined;
		try {
			const rows = await api.get<ProjectQuota[]>('/api/v1/admin/overview/projects', token, projectId);
			const map = new Map<string, ProjectQuota>();
			for (const r of rows) map.set(r.project_id, r);
			adminProjectQuotas = map;
		} catch {
			adminProjectQuotas = new Map();
		}
	}

	async function loadAdminProjects() {
		if (!opts.adminMode()) return;
		adminProjectsLoading = true;
		const token = get(auth).token ?? undefined;
		const projectId = get(auth).projectId ?? undefined;
		try {
			const res = await api.get<{ id: string; name: string }[]>('/api/v1/admin/projects/names', token, projectId);
			adminProjects = res.map(p => ({ id: p.id, name: p.name }));
		} catch {
			adminProjects = [];
		} finally {
			adminProjectsLoading = false;
		}
		loadAdminProjectQuotas();
	}

	async function loadData() {
		loading = true;
		loadError = '';
		const token = get(auth).token ?? undefined;
		const projectId = get(auth).projectId ?? undefined;
		try {
			if (opts.adminMode() && adminSelectedProjectId) {
				const pid = adminSelectedProjectId;
				[images, flavors, libraries] = await Promise.all([
					api.get<VmImage[]>('/api/v1/images', token, projectId),
					api.get<VmFlavor[]>('/api/v1/flavors', token, projectId),
					api.get<LibraryItem[]>('/api/v1/libraries', token, projectId),
				]);
				[networks, volumes] = await Promise.all([
					api.get<NetworkInfo[]>(`/api/v1/admin/instances/networks-for-project?project_id=${pid}`, token, projectId).catch(() => [] as NetworkInfo[]),
					api.get<Volume[]>(`/api/v1/admin/instances/volumes-for-project?project_id=${pid}`, token, projectId).catch(() => [] as Volume[]),
				]);
				keypairs = [];
				try {
					securityGroups = await api.get<SecurityGroupInfo[]>(
						`/api/v1/admin/instances/security-groups-for-project?project_id=${pid}`, token, projectId,
					);
				} catch { securityGroups = []; }
				availabilityZones = [];
				try {
					availabilityZones = await api.get<AvailabilityZoneInfo[]>('/api/v1/instances/availability-zones', token, projectId);
				} catch { /* 무시 */ }
			} else {
				[images, flavors, libraries, networks, keypairs, volumes] = await Promise.all([
					api.get<VmImage[]>('/api/v1/images', token, projectId),
					api.get<VmFlavor[]>('/api/v1/flavors', token, projectId),
					api.get<LibraryItem[]>('/api/v1/libraries', token, projectId),
					api.get<NetworkInfo[]>('/api/v1/networks', token, projectId),
					api.get<KeypairInfo[]>('/api/v1/keypairs', token, projectId),
					api.get<Volume[]>('/api/v1/volumes', token, projectId),
				]);
				await loadSquashfsCatalog();
				try {
					securityGroups = await api.get<SecurityGroupInfo[]>('/api/v1/security-groups', token, projectId);
				} catch { securityGroups = []; }
				try {
					availabilityZones = await api.get<AvailabilityZoneInfo[]>('/api/v1/instances/availability-zones', token, projectId);
				} catch { availabilityZones = []; }
				try {
					fileStorages = await api.get<typeof fileStorages>('/api/v1/storage/file-storages', token, projectId);
				} catch { fileStorages = []; }

				if (keypairs.length === 1 && !get(wizard).keyName) {
					wizard.update(w => ({ ...w, keyName: keypairs[0].name }));
				}
				if (networks.length > 0 && !get(wizard).networkId) {
					let selectedNet = networks[0];
					try {
						const defaultRecord = await api.get<{ network_id: string }>('/api/v1/networks/default', token, projectId);
						defaultNetworkId = defaultRecord.network_id;
						const found = networks.find(n => n.id === defaultRecord.network_id);
						if (found) selectedNet = found;
					} catch {
						const byName = networks.find(n => n.name === 'Default');
						if (byName) selectedNet = byName;
					}
					wizard.update(w => ({ ...w, networkId: selectedNet.id, networkName: selectedNet.name }));
				} else if (get(wizard).networkId) {
					try {
						const defaultRecord = await api.get<{ network_id: string }>('/api/v1/networks/default', token, projectId);
						defaultNetworkId = defaultRecord.network_id;
					} catch { /* 무시 */ }
				}
			}
			if (securityGroups.length > 0 && get(wizard).securityGroups.length === 0) {
				const defaultSg = securityGroups.find(sg => sg.name === 'default');
				if (defaultSg) wizard.update(w => ({ ...w, securityGroups: [defaultSg.name] }));
			}
			if (opts.adminMode() && networks.length > 0 && !get(wizard).networkId) {
				const net = networks[0];
				wizard.update(w => ({ ...w, networkId: net.id, networkName: net.name }));
			}
		} catch (e) {
			loadError = e instanceof ApiError ? `데이터 로드 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	function selectAdminProject(id: string, name: string) {
		adminSelectedProjectId = id;
		adminSelectedProjectName = name;
		wizard.update(w => ({ ...w, networkId: null, networkName: null, securityGroups: [], keyName: null }));
		loadData();
		loadFlavorQuota();
	}

	function handleReset() {
		resetWizard();
		adminSelectedProjectId = null;
		adminSelectedProjectName = null;
		if (opts.adminMode()) {
			loadAdminProjects();
		} else {
			loadData();
		}
	}

	function nextStep() {
		if (get(wizard).step < TOTAL_STEPS) wizard.update(w => ({ ...w, step: w.step + 1 }));
	}

	function prevStep() {
		if (get(wizard).step > 1) wizard.update(w => ({ ...w, step: w.step - 1 }));
	}

	function goTo(step: number) { wizard.update(w => ({ ...w, step })); }

	function selectImage(id: string, name: string) { wizard.update(w => ({ ...w, imageId: id, imageName: name })); }
	function selectFlavor(id: string, name: string) { wizard.update(w => ({ ...w, flavorId: id, flavorName: name })); }

	function toggleLibrary(id: string, _deps: string[]) {
		wizard.update(w => {
			const libs = new Set(w.libraries);
			if (libs.has(id)) {
				libs.delete(id);
			} else {
				resolveAllDeps(id).forEach(d => libs.add(d));
			}
			const newLibs = Array.from(libs);
			const newStrategy = newLibs.length === 0 ? null : (w.strategy ?? 'prebuilt');
			return { ...w, libraries: newLibs, strategy: newStrategy };
		});
	}

	function selectStrategy(s: 'prebuilt' | 'dynamic' | null) { wizard.update(w => ({ ...w, strategy: s })); }
	function selectScheduling(s: 'standard' | 'ha') {
		wizard.update(w => ({ ...w, scheduling: normalizeSchedulingForBeta(betaState, s) }));
	}
	function selectMountProtocol(p: 'CEPHFS' | 'NFS') { wizard.update(w => ({ ...w, mountProtocol: p })); }

	function selectNetwork(id: string | null) {
		const net = networks.find(n => n.id === id) ?? null;
		wizard.update(w => ({ ...w, networkId: id, networkName: net?.name ?? null }));
	}

	function clearSquashfsSelection() {
		wizard.update(w => ({ ...w, squashfsMode: null, layerProfileName: null, layerArtifactIds: [] }));
	}

	function selectSquashfsMode(mode: 'profile' | 'artifacts' | null) {
		wizard.update(w => ({
			...w,
			squashfsMode: mode,
			layerProfileName: mode === 'profile' ? w.layerProfileName : null,
			layerArtifactIds: mode === 'artifacts' ? w.layerArtifactIds : [],
			libraries: mode ? [] : w.libraries,
			templateName: mode ? null : w.templateName,
			templateVersion: mode ? null : w.templateVersion,
			strategy: mode ? null : w.strategy,
		}));
	}

	function selectSquashfsProfile(name: string | null) {
		wizard.update(w => ({
			...w,
			squashfsMode: name ? 'profile' : w.squashfsMode,
			layerProfileName: name,
			layerArtifactIds: [],
			libraries: name ? [] : w.libraries,
			templateName: name ? null : w.templateName,
			templateVersion: name ? null : w.templateVersion,
			strategy: name ? null : w.strategy,
		}));
	}

	function toggleSquashfsArtifact(id: number) {
		wizard.update(w => {
			const ids = new Set(w.layerArtifactIds);
			if (ids.has(id)) {
				ids.delete(id);
			} else {
				lineageIdsForArtifact(id).forEach(lineageId => ids.add(lineageId));
			}
			const nextIds = Array.from(ids);
			return {
				...w,
				squashfsMode: nextIds.length > 0 ? 'artifacts' : w.squashfsMode,
				layerArtifactIds: nextIds,
				layerProfileName: null,
				libraries: nextIds.length > 0 ? [] : w.libraries,
				templateName: nextIds.length > 0 ? null : w.templateName,
				templateVersion: nextIds.length > 0 ? null : w.templateVersion,
				strategy: nextIds.length > 0 ? null : w.strategy,
			};
		});
	}

	async function deploy() {
		deployError = '';
		deploying = true;
		currentStep = 'manila_preparing';
		progress = 0;
		progressMessage = '배포 시작...';

		const baseUrl = getBaseUrl();
		const authState = get(auth);
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			'Accept': 'text/event-stream',
		};
		if (authState.token) headers['Authorization'] = `Bearer ${authState.token}`;
		if (authState.projectId) headers['X-Project-Id'] = authState.projectId;

		const endpoint = opts.adminMode()
			? `${baseUrl}/api/v1/admin/instances/async`
			: `${baseUrl}/api/v1/instances/async`;

		const w = get(wizard);
		const useSquashfsConsume = shouldUseSquashfsConsume({
			beta: betaState,
			adminMode: opts.adminMode(),
			bootSource: w.bootSource,
			selectedImageUbuntuBase,
			squashfsMode: w.squashfsMode,
			layerProfileName: w.layerProfileName,
			layerArtifactIds: w.layerArtifactIds,
			squashfsBaseMismatch,
		});
		if (useSquashfsConsume) {
			const consumeBody: Record<string, unknown> = {
				server_name: w.instanceName,
				flavor_id: w.flavorId,
				image_id: w.imageId,
				network_id: w.networkId,
				key_name: w.keyName || null,
				...(w.squashfsMode === 'profile'
					? { profile_name: w.layerProfileName }
					: { artifact_ids: w.layerArtifactIds }),
			};
			try {
				currentStep = 'server_creating';
				progress = 60;
				progressMessage = 'squashfs 라이브러리 소비 VM 생성 중...';
				const response = await fetch(`${baseUrl}/api/v1/libraries/squashfs/consume`, {
					method: 'POST',
					headers: { ...headers, Accept: 'application/json' },
					body: JSON.stringify(consumeBody),
				});
				if (!response.ok) {
					const text = await response.text();
					throw new ApiError(response.status, text || response.statusText);
				}
				currentStep = 'completed';
				progress = 100;
				progressMessage = '배포 완료';
				toast.success('인스턴스 생성 완료');
				setTimeout(() => {
					resetWizard();
					closeWizard();
					goto('/dashboard');
				}, 1000);
				return;
			} catch (e) {
				deployError = e instanceof ApiError
					? `배포 실패: ${e.message}`
					: `서버 연결 오류: ${e instanceof Error ? e.message : '알 수 없는 오류'}`;
				toast.error(`인스턴스 생성 실패: ${deployError}`);
				deploying = false;
				return;
			}
		}

		const body: Record<string, unknown> = {
			name: w.instanceName,
			...(w.bootSource === 'volume'
				? { boot_volume_id: w.bootVolumeId }
				: {
					image_id: w.imageId,
					boot_volume_size_gb: w.bootVolumeSizeGb,
					delete_boot_volume_on_termination: w.deleteBootVolumeOnTermination,
				}),
			flavor_id: w.flavorId,
			libraries: w.libraries,
			strategy: w.strategy,
			scheduling: normalizeSchedulingForBeta(betaState, w.scheduling),
			network_id: w.networkId,
			key_name: w.keyName || null,
			availability_zone: w.availabilityZone,
			security_groups: w.securityGroups,
			userdata: w.cloudInit || null,
			data_mounts: w.dataMounts.map(m => ({
				file_storage_id: m.fileStorageId,
				mount_point: m.mountPoint,
				read_only: m.readOnly,
			})),
		};
		if (opts.adminMode() && adminSelectedProjectId) {
			body.project_id = adminSelectedProjectId;
		}

		try {
			const response = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(body) });
			if (!response.ok) {
				const text = await response.text();
				throw new ApiError(response.status, text || response.statusText);
			}
			const reader = response.body?.getReader();
			if (!reader) throw new Error('No response body');
			const decoder = new TextDecoder();
			let buffer = '';
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;
				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';
				for (const line of lines) {
					if (line.startsWith('data: ')) {
						try {
							const data = JSON.parse(line.slice(6)) as ProgressMessage;
							currentStep = data.step;
							progress = data.progress;
							progressMessage = data.message;
							if (data.elapsed_seconds !== undefined && data.elapsed_seconds !== null) {
								elapsedSeconds = data.elapsed_seconds;
							}
							if (data.step === 'completed') {
								toast.success(`인스턴스 생성 완료`);
								setTimeout(() => {
									resetWizard();
									adminSelectedProjectId = null;
									adminSelectedProjectName = null;
									closeWizard();
									goto(opts.adminMode() ? '/admin/instances' : '/dashboard');
								}, 1000);
								return;
							}
							if (data.step === 'failed') {
								deployError = data.error || data.message;
								toast.error(`인스턴스 생성 실패: ${deployError}`);
								deploying = false;
								return;
							}
						} catch { /* JSON 파싱 실패 시 무시 */ }
					}
				}
			}
		} catch (e) {
			deployError = e instanceof ApiError
				? `배포 실패: ${e.message}`
				: `서버 연결 오류: ${e instanceof Error ? e.message : '알 수 없는 오류'}`;
			deploying = false;
		}
	}

	function init() {
		if (opts.adminMode()) {
			const targetId = get(wizard).targetProjectId;
			if (targetId) {
				adminSelectedProjectId = targetId;
				const found = adminProjects.find(p => p.id === targetId);
				adminSelectedProjectName = found?.name ?? targetId;
				loadData();
				loadFlavorQuota();
			}
			loadAdminProjects();
		} else {
			loadData();
			loadFlavorQuota();
		}
	}

	return {
		// Opts passthrough
		get adminMode() { return opts.adminMode(); },
		// Wizard state mirror (for sub-components that need form state without $ prefix)
		get wizardState() { return wizardState; },
		// Data state
		get images() { return images; },
		get flavors() { return flavors; },
		get libraries() { return libraries; },
		get networks() { return networks; },
		get keypairs() { return keypairs; },
		get volumes() { return volumes; },
		get fileStorages() { return fileStorages; },
		get securityGroups() { return securityGroups; },
		get availabilityZones() { return availabilityZones; },
		get defaultNetworkId() { return defaultNetworkId; },
		get flavorQuota() { return flavorQuota; },
		get squashfsProfiles() { return squashfsProfiles; },
		get squashfsArtifacts() { return squashfsArtifacts; },
		// UI state
		get loading() { return loading; },
		get loadError() { return loadError; },
		get deploying() { return deploying; },
		get deployError() { return deployError; },
		get currentStep() { return currentStep; },
		get progress() { return progress; },
		get progressMessage() { return progressMessage; },
		get elapsedSeconds() { return elapsedSeconds; },
		// Admin state
		get adminProjects() { return adminProjects; },
		get adminProjectsLoading() { return adminProjectsLoading; },
		get adminProjectQuotas() { return adminProjectQuotas; },
		get adminProjectSearch() { return adminProjectSearch; },
		set adminProjectSearch(v: string) { adminProjectSearch = v; },
		get adminSelectedProjectId() { return adminSelectedProjectId; },
		get adminSelectedProjectName() { return adminSelectedProjectName; },
		// Derived
		get filteredAdminProjects() { return filteredAdminProjects; },
		get progressSteps() { return progressSteps; },
		get ubuntuVersion() { return ubuntuVersion; },
		get selectedNetwork() { return selectedNetwork; },
		get selectedImage() { return selectedImage; },
		get selectedImageUbuntuBase() { return selectedImageUbuntuBase; },
		get squashfsEligible() { return squashfsEligible; },
		get selectedSquashfsArtifacts() { return selectedSquashfsArtifacts; },
		get squashfsBaseMismatch() { return squashfsBaseMismatch; },
		get squashfsSelectionReady() { return squashfsSelectionReady; },
		get hasGpuFlavor() { return hasGpuFlavor; },
		get hasPrebuilt() { return hasPrebuilt; },
		get selectedFlavorDetail() { return selectedFlavorDetail; },
		get canNext() { return canNext; },
		get needsProjectSelect() { return needsProjectSelect; },
		// Helpers
		fmtRemaining,
		isExhausted,
		// Lifecycle
		init,
		// Data loading
		loadData,
		loadFlavorQuota,
		loadAdminProjects,
		loadSquashfsCatalog,
		// Actions
		selectAdminProject,
		handleReset,
		nextStep,
		prevStep,
		goTo,
		selectImage,
		selectFlavor,
		toggleLibrary,
		selectStrategy,
		selectScheduling,
		selectMountProtocol,
		selectNetwork,
		clearSquashfsSelection,
		selectSquashfsMode,
		selectSquashfsProfile,
		toggleSquashfsArtifact,
		deploy,
	};
}
