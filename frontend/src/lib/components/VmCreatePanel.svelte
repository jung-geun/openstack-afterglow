<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { wizard, resetWizard, closeWizard } from '$lib/stores/wizard';
	import { api, ApiError, getBaseUrl } from '$lib/api/client';
	import { toast } from '$lib/stores/toast';
	import SelectImage from '$lib/components/wizard/SelectImage.svelte';
	import SelectFlavor from '$lib/components/wizard/SelectFlavor.svelte';
	import SelectLibraries from '$lib/components/wizard/SelectLibraries.svelte';
	import SelectTemplate from '$lib/components/wizard/SelectTemplate.svelte';
	import SelectStrategy from '$lib/components/wizard/SelectStrategy.svelte';
	import WizardStepper from '$lib/components/wizard/WizardStepper.svelte';
	import WizardHeader from '$lib/components/wizard/WizardHeader.svelte';
	import WizardFooter from '$lib/components/wizard/WizardFooter.svelte';
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import type { Volume } from '$lib/types/resources';

	interface Props {
		adminMode?: boolean;
	}
	let { adminMode = false }: Props = $props();

	const TOTAL_STEPS = 6;

	interface ProgressMessage {
		step: string;
		progress: number;
		message: string;
		instance_id?: string;
		error?: string;
		elapsed_seconds?: number | null;
	}

	interface NetworkInfo {
		id: string;
		name: string;
		status: string;
		is_external: boolean;
		is_shared: boolean;
	}

	interface KeypairInfo {
		name: string;
		fingerprint: string;
		type: string;
	}

	interface SecurityGroupInfo {
		id: string;
		name: string;
		description: string;
	}

	interface AvailabilityZoneInfo {
		name: string;
		state: boolean;
	}

	const ALL_PROGRESS_STEPS = [
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

	let progressSteps = $derived(
		$wizard.libraries.length > 0
			? ALL_PROGRESS_STEPS
			: ALL_PROGRESS_STEPS.filter(s => !s.needsLibrary)
	);

	let images = $state<any[]>([]);
	let flavors = $state<any[]>([]);
	let libraries = $state<any[]>([]);
	let networks = $state<NetworkInfo[]>([]);
	let keypairs = $state<KeypairInfo[]>([]);
	let volumes = $state<Volume[]>([]);
	let securityGroups = $state<SecurityGroupInfo[]>([]);
	let availabilityZones = $state<AvailabilityZoneInfo[]>([]);
	let defaultNetworkId = $state<string | null>(null);
	let loadError = $state('');
	let deploying = $state(false);
	let deployError = $state('');
	let currentStep = $state('manila_preparing');
	let progress = $state(0);
	let progressMessage = $state('');
	let elapsedSeconds = $state<number | null>(null);
	let loading = $state(false);

	// admin 모드 전용 상태
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
	let adminProjects = $state<ProjectInfo[]>([]);
	let adminProjectsLoading = $state(false);
	let adminProjectQuotas = $state<Map<string, ProjectQuota>>(new Map());
	let adminProjectSearch = $state('');
	// $wizard.targetProjectId가 이미 설정된 경우(볼륨 → VM 진입) 그대로 사용
	let adminSelectedProjectId = $state<string | null>(null);
	let adminSelectedProjectName = $state<string | null>(null);

	let filteredAdminProjects = $derived.by(() => {
		const q = adminProjectSearch.trim().toLowerCase();
		if (!q) return adminProjects;
		return adminProjects.filter(p =>
			p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)
		);
	});

	// 플레이버 단계용 정규화된 quota (user/admin 양쪽 호환)
	interface FlavorQuotaSummary {
		instances?: { limit: number; in_use: number };
		cores?: { limit: number; in_use: number };
		ram?: { limit: number; in_use: number };       // MB
		gigabytes?: { limit: number; in_use: number }; // GB
	}
	let flavorQuota = $state<FlavorQuotaSummary | null>(null);

	async function loadFlavorQuota() {
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			if (adminMode && adminSelectedProjectId) {
				// admin: os-quota-sets/{pid}/detail REST 직접 호출이라 정확한 값 반환
				const r = await api.get<{ compute?: any; volume?: any }>(
					`/api/admin/quotas/${encodeURIComponent(adminSelectedProjectId)}`,
					token, projectId,
				);
				flavorQuota = {
					instances: r.compute?.instances,
					cores: r.compute?.cores,
					ram: r.compute?.ram,
					gigabytes: r.volume?.gigabytes,
				};
			} else if (!adminMode) {
				// user: /api/dashboard/quotas는 openstacksdk get_quota_set 파싱 이슈로
				// 모든 값이 -1로 나오는 케이스가 있어 limits API 기반의 summary를 사용
				const r = await api.get<{
					compute?: { instances_used?: number; instances_limit?: number;
						vcpus_used?: number; vcpus_limit?: number;
						ram_used_mb?: number; ram_limit_mb?: number };
					storage?: { gigabytes_used?: number; gigabytes_limit?: number };
				}>('/api/dashboard/summary', token, projectId);
				const c = r.compute ?? {};
				const s = r.storage ?? {};
				flavorQuota = {
					instances: { limit: c.instances_limit ?? -1, in_use: c.instances_used ?? 0 },
					cores: { limit: c.vcpus_limit ?? -1, in_use: c.vcpus_used ?? 0 },
					ram: { limit: c.ram_limit_mb ?? -1, in_use: c.ram_used_mb ?? 0 },
					gigabytes: { limit: s.gigabytes_limit ?? -1, in_use: s.gigabytes_used ?? 0 },
				};
			}
		} catch {
			flavorQuota = null;
		}
	}

	// admin 모드에서 프로젝트 목록 로드
	async function loadAdminProjects() {
		if (!adminMode) return;
		adminProjectsLoading = true;
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			const res = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', token, projectId);
			adminProjects = res.map(p => ({ id: p.id, name: p.name }));
		} catch {
			adminProjects = [];
		} finally {
			adminProjectsLoading = false;
		}
		loadAdminProjectQuotas();
	}

	// 프로젝트별 quota 정보 로드 (백그라운드, 실패해도 목록은 표시)
	async function loadAdminProjectQuotas() {
		if (!adminMode) return;
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			const rows = await api.get<ProjectQuota[]>('/api/admin/overview/projects', token, projectId);
			const map = new Map<string, ProjectQuota>();
			for (const r of rows) map.set(r.project_id, r);
			adminProjectQuotas = map;
		} catch {
			adminProjectQuotas = new Map();
		}
	}

	function fmtRemaining(p?: QuotaPair): string {
		if (!p) return '-';
		if (p.quota < 0) return '∞';
		return String(Math.max(0, p.quota - p.used));
	}

	function isExhausted(p?: QuotaPair): boolean {
		if (!p) return false;
		if (p.quota < 0) return false;
		return p.used >= p.quota;
	}

	function selectAdminProject(id: string, name: string) {
		adminSelectedProjectId = id;
		adminSelectedProjectName = name;
		wizard.update(w => ({ ...w, networkId: null, networkName: null, securityGroups: [], keyName: null }));
		loadData();
		loadFlavorQuota();
	}

	// admin 모드에서 선택된 프로젝트 기반으로 admin 엔드포인트 사용
	async function loadData() {
		loading = true;
		loadError = '';
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			if (adminMode && adminSelectedProjectId) {
				const pid = adminSelectedProjectId;
				[images, flavors, libraries] = await Promise.all([
					api.get<any[]>('/api/images', token, projectId),
					api.get<any[]>('/api/flavors', token, projectId),
					api.get<any[]>('/api/libraries', token, projectId),
				]);
				// admin 전용 프로젝트 리소스
				[networks, volumes] = await Promise.all([
					api.get<NetworkInfo[]>(`/api/admin/instances/networks-for-project?project_id=${pid}`, token, projectId).catch(() => [] as NetworkInfo[]),
					api.get<Volume[]>(`/api/admin/instances/volumes-for-project?project_id=${pid}`, token, projectId).catch(() => [] as Volume[]),
				]);
				keypairs = []; // admin은 대상 프로젝트 키페어 조회 불가
				try {
					securityGroups = await api.get<SecurityGroupInfo[]>(
						`/api/admin/instances/security-groups-for-project?project_id=${pid}`,
						token, projectId,
					);
				} catch { securityGroups = []; }
				availabilityZones = [];
				try {
					availabilityZones = await api.get<AvailabilityZoneInfo[]>('/api/instances/availability-zones', token, projectId);
				} catch { /* 무시 */ }
			} else {
				[images, flavors, libraries, networks, keypairs, volumes] = await Promise.all([
					api.get<any[]>('/api/images', token, projectId),
					api.get<any[]>('/api/flavors', token, projectId),
					api.get<any[]>('/api/libraries', token, projectId),
					api.get<NetworkInfo[]>('/api/networks', token, projectId),
					api.get<KeypairInfo[]>('/api/keypairs', token, projectId),
					api.get<Volume[]>('/api/volumes', token, projectId),
				]);
				try {
					securityGroups = await api.get<SecurityGroupInfo[]>('/api/security-groups', token, projectId);
				} catch { securityGroups = []; }
				try {
					availabilityZones = await api.get<AvailabilityZoneInfo[]>('/api/instances/availability-zones', token, projectId);
				} catch { availabilityZones = []; }

				if (keypairs.length === 1 && !$wizard.keyName) {
					wizard.update(w => ({ ...w, keyName: keypairs[0].name }));
				}
				if (networks.length > 0 && !$wizard.networkId) {
					let selectedNet = networks[0];
					try {
						const defaultRecord = await api.get<{ network_id: string }>('/api/networks/default', token, projectId);
						defaultNetworkId = defaultRecord.network_id;
						const found = networks.find(n => n.id === defaultRecord.network_id);
						if (found) selectedNet = found;
					} catch {
						const byName = networks.find(n => n.name === 'Default');
						if (byName) selectedNet = byName;
					}
					wizard.update(w => ({ ...w, networkId: selectedNet.id, networkName: selectedNet.name }));
				} else if ($wizard.networkId) {
					try {
						const defaultRecord = await api.get<{ network_id: string }>('/api/networks/default', token, projectId);
						defaultNetworkId = defaultRecord.network_id;
					} catch { /* 무시 */ }
				}
			}
			// 보안 그룹 기본 선택 (default)
			if (securityGroups.length > 0 && $wizard.securityGroups.length === 0) {
				const defaultSg = securityGroups.find(sg => sg.name === 'default');
				if (defaultSg) wizard.update(w => ({ ...w, securityGroups: [defaultSg.name] }));
			}
			// admin 모드: 네트워크 기본 선택
			if (adminMode && networks.length > 0 && !$wizard.networkId) {
				const net = networks[0];
				wizard.update(w => ({ ...w, networkId: net.id, networkName: net.name }));
			}
		} catch (e) {
			loadError = e instanceof ApiError ? `데이터 로드 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		if (adminMode) {
			// targetProjectId가 이미 설정된 경우 (볼륨에서 진입)
			if ($wizard.targetProjectId) {
				adminSelectedProjectId = $wizard.targetProjectId;
				const found = adminProjects.find(p => p.id === $wizard.targetProjectId);
				adminSelectedProjectName = found?.name ?? $wizard.targetProjectId;
				loadData();
				loadFlavorQuota();
			}
			loadAdminProjects();
		} else {
			loadData();
			loadFlavorQuota();
		}
	});

	function handleReset() {
		resetWizard();
		adminSelectedProjectId = null;
		adminSelectedProjectName = null;
		if (adminMode) {
			loadAdminProjects();
		} else {
			loadData();
		}
	}

	function nextStep() {
		if ($wizard.step < TOTAL_STEPS) {
			wizard.update(w => ({ ...w, step: w.step + 1 }));
		}
	}
	function prevStep() {
		if ($wizard.step > 1) {
			wizard.update(w => ({ ...w, step: w.step - 1 }));
		}
	}

	function goTo(step: number) {
		wizard.update(w => ({ ...w, step }));
	}

	function selectImage(id: string, name: string) {
		wizard.update(w => ({ ...w, imageId: id, imageName: name }));
	}
	function selectFlavor(id: string, name: string) {
		wizard.update(w => ({ ...w, flavorId: id, flavorName: name }));
	}

	function resolveAllDeps(id: string): string[] {
		const result: string[] = [];
		const visited = new Set<string>();
		function visit(lid: string) {
			if (visited.has(lid)) return;
			visited.add(lid);
			const lib = libraries.find((l: any) => l.id === lid);
			if (lib) (lib.depends_on as string[]).forEach(d => visit(d));
			result.push(lid);
		}
		visit(id);
		return result;
	}

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

	const ubuntuVersion = $derived.by(() => {
		const name = $wizard.imageName ?? '';
		const m = name.match(/(\d{2}\.\d{2})/);
		return m ? m[1] : undefined;
	});

	function selectStrategy(s: 'prebuilt' | 'dynamic' | null) {
		wizard.update(w => ({ ...w, strategy: s }));
	}

	function selectScheduling(s: 'standard' | 'ha') {
		wizard.update(w => ({ ...w, scheduling: s }));
	}

	function selectMountProtocol(p: 'CEPHFS' | 'NFS') {
		wizard.update(w => ({ ...w, mountProtocol: p }));
	}

	function selectNetwork(id: string | null) {
		const net = networks.find(n => n.id === id) ?? null;
		wizard.update(w => ({ ...w, networkId: id, networkName: net?.name ?? null }));
	}

	let selectedNetwork = $derived(
		$wizard.networkId ? networks.find(n => n.id === $wizard.networkId) ?? null : null
	);

	let hasGpuFlavor = $derived(
		flavors.find(f => f.id === $wizard.flavorId)
			? Object.keys(flavors.find(f => f.id === $wizard.flavorId)?.extra_specs ?? {}).some(
					k => k.toLowerCase().includes('gpu')
				)
			: false
	);

	let hasPrebuilt = $derived(
		libraries.some(l => $wizard.libraries.includes(l.id) && l.available_prebuilt)
	);

	let selectedFlavorDetail = $derived.by(() => {
		const f = flavors.find((fl: any) => fl.id === $wizard.flavorId);
		if (!f) return '';
		const parts = [`${f.vcpus} vCPU`, `${f.ram >= 1024 ? Math.round(f.ram / 1024) + ' GB' : f.ram + ' MB'}`, `${f.disk} GB`];
		const alias = f.extra_specs?.['pci_passthrough:alias'] ?? '';
		if (alias) {
			const gpuParts = alias.split(',').filter((e: string) => e.includes(':') && !e.toLowerCase().includes('audio'));
			if (gpuParts.length > 0) {
				gpuParts.forEach((e: string) => {
					const idx = e.lastIndexOf(':');
					const model = e.slice(0, idx).trim();
					const count = parseInt(e.slice(idx + 1)) || 1;
					parts.push(`${model} ${count > 1 ? '× ' + count : ''}`);
				});
			}
		}
		return parts.join(' · ');
	});

	// admin 모드에서는 키페어 없이도 배포 가능
	let canNext = $derived((() => {
		switch ($wizard.step) {
			case 1: return $wizard.bootSource === 'volume' ? !!$wizard.bootVolumeId : !!$wizard.imageId;
			case 2: return !!$wizard.flavorId;
			case 3: return true;
			case 4: {
				if (!$wizard.scheduling) return false;
				if ($wizard.libraries.length > 0 && !$wizard.strategy) return false;
				return true;
			}
			case 5: return !!$wizard.instanceName.trim() && (adminMode || !!$wizard.keyName);
			case 6: return !!$wizard.instanceName.trim();
			default: return false;
		}
	})());

	async function deploy() {
		deployError = '';
		deploying = true;
		currentStep = 'manila_preparing';
		progress = 0;
		progressMessage = '배포 시작...';

		const baseUrl = getBaseUrl();
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			'Accept': 'text/event-stream'
		};
		if ($auth.token) headers['X-Auth-Token'] = $auth.token;
		if ($auth.projectId) headers['X-Project-Id'] = $auth.projectId;

		const endpoint = adminMode
			? `${baseUrl}/api/admin/instances/async`
			: `${baseUrl}/api/instances/async`;

		const body: Record<string, unknown> = {
			name: $wizard.instanceName,
			...($wizard.bootSource === 'volume'
				? { boot_volume_id: $wizard.bootVolumeId }
				: {
					image_id: $wizard.imageId,
					boot_volume_size_gb: $wizard.bootVolumeSizeGb,
					delete_boot_volume_on_termination: $wizard.deleteBootVolumeOnTermination,
				}),
			flavor_id: $wizard.flavorId,
			libraries: $wizard.libraries,
			strategy: $wizard.strategy,
			scheduling: $wizard.scheduling,
			network_id: $wizard.networkId,
			key_name: $wizard.keyName || null,
			availability_zone: $wizard.availabilityZone,
			security_groups: $wizard.securityGroups,
			userdata: $wizard.cloudInit || null,
		};
		if (adminMode && adminSelectedProjectId) {
			body.project_id = adminSelectedProjectId;
		}

		try {
			const response = await fetch(endpoint, {
				method: 'POST',
				headers,
				body: JSON.stringify(body),
			});

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
									goto(adminMode ? '/admin/instances' : '/dashboard');
								}, 1000);
								return;
							}

							if (data.step === 'failed') {
								deployError = data.error || data.message;
								toast.error(`인스턴스 생성 실패: ${deployError}`);
								deploying = false;
								return;
							}
						} catch {
							// JSON 파싱 실패 시 무시
						}
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

	const stepLabels = ['이미지', '플레이버', '라이브러리', '전략', '설정', '배포'];
	const stepSubtitles: Record<number, string> = {
		1: '이미지',
		2: '플레이버',
		3: '라이브러리',
		4: '전략',
		5: '설정',
		6: '배포',
	};

	// admin 모드: 프로젝트 미선택 상태
	let needsProjectSelect = $derived(adminMode && !adminSelectedProjectId);
</script>

<SlidePanel onClose={closeWizard} width="w-full md:w-[75vw] max-w-4xl">
	<div class="p-4 md:p-8">
		{#if needsProjectSelect}
			<!-- admin 모드: 프로젝트 선택 -->
			<div class="flex items-start justify-between mb-6">
				<div>
					<h1 class="text-xl font-bold text-white">VM 생성 <span class="text-sm font-normal text-amber-400 ml-1">관리자</span></h1>
					<p class="text-sm text-gray-500 mt-0.5">대상 프로젝트 선택</p>
				</div>
				<button
					onclick={closeWizard}
					class="text-gray-500 hover:text-white transition-colors p-1 rounded hover:bg-gray-800"
					aria-label="닫기"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
					</svg>
				</button>
			</div>
			<p class="text-sm text-gray-400 mb-4">VM을 생성할 프로젝트를 선택하세요. 선택한 프로젝트의 네트워크, 볼륨, 보안 그룹을 사용합니다.</p>
			{#if adminProjectsLoading}
				<div class="flex items-center justify-center py-10">
					<LoadingSpinner size="md" color="blue">프로젝트 로드 중...</LoadingSpinner>
				</div>
			{:else if adminProjects.length === 0}
				<div class="text-center py-10 text-gray-500 text-sm">프로젝트 목록을 불러올 수 없습니다.</div>
			{:else}
				<div class="relative mb-3">
					<svg class="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M10 18a8 8 0 100-16 8 8 0 000 16z"/>
					</svg>
					<input
						type="text"
						bind:value={adminProjectSearch}
						placeholder="프로젝트 이름 또는 ID 검색..."
						class="w-full bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg pl-9 pr-9 py-2 focus:outline-none focus:border-blue-500 placeholder-gray-500"
					/>
					{#if adminProjectSearch}
						<button
							onclick={() => (adminProjectSearch = '')}
							class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-sm"
							aria-label="검색어 지우기"
						>✕</button>
					{/if}
				</div>
				{#if filteredAdminProjects.length === 0}
					<div class="text-center py-10 text-gray-500 text-sm">검색 결과가 없습니다.</div>
				{:else}
					<div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
						{#each filteredAdminProjects as proj}
							{@const q = adminProjectQuotas.get(proj.id)}
							<button
								onclick={() => selectAdminProject(proj.id, proj.name)}
								class="w-full text-left px-4 py-3 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-500 transition-colors"
							>
								<div class="flex items-start justify-between gap-3">
									<div class="min-w-0 flex-1">
										<div class="text-white text-sm font-medium truncate">{proj.name}</div>
										<div class="text-gray-500 text-xs font-mono mt-0.5 truncate">{proj.id}</div>
									</div>
									{#if adminProjectQuotas.size === 0}
										<div class="text-gray-600 text-xs flex-shrink-0">quota 로딩 중...</div>
									{:else if q}
										<div class="flex flex-wrap items-center gap-1.5 flex-shrink-0 justify-end">
											<span class="px-1.5 py-0.5 rounded text-[11px] font-mono {isExhausted(q.instances) ? 'bg-red-900/40 text-red-300 border border-red-800/50' : 'bg-gray-900 text-gray-400 border border-gray-700'}" title="남은 인스턴스 (사용 {q.instances?.used ?? 0} / {q.instances?.quota < 0 ? '∞' : q.instances?.quota})">
												VM {fmtRemaining(q.instances)}
											</span>
											<span class="px-1.5 py-0.5 rounded text-[11px] font-mono {isExhausted(q.cpu) ? 'bg-red-900/40 text-red-300 border border-red-800/50' : 'bg-gray-900 text-gray-400 border border-gray-700'}" title="남은 vCPU (사용 {q.cpu?.used ?? 0} / {q.cpu?.quota < 0 ? '∞' : q.cpu?.quota})">
												CPU {fmtRemaining(q.cpu)}
											</span>
											<span class="px-1.5 py-0.5 rounded text-[11px] font-mono {isExhausted(q.ram_mb) ? 'bg-red-900/40 text-red-300 border border-red-800/50' : 'bg-gray-900 text-gray-400 border border-gray-700'}" title="남은 RAM MB (사용 {q.ram_mb?.used ?? 0} / {q.ram_mb?.quota < 0 ? '∞' : q.ram_mb?.quota})">
												RAM {q.ram_mb && q.ram_mb.quota >= 0 ? Math.max(0, Math.floor((q.ram_mb.quota - q.ram_mb.used) / 1024)) + 'GB' : '∞'}
											</span>
											<span class="px-1.5 py-0.5 rounded text-[11px] font-mono {isExhausted(q.disk_gb) ? 'bg-red-900/40 text-red-300 border border-red-800/50' : 'bg-gray-900 text-gray-400 border border-gray-700'}" title="남은 디스크 GB (사용 {q.disk_gb?.used ?? 0} / {q.disk_gb?.quota < 0 ? '∞' : q.disk_gb?.quota})">
												DISK {fmtRemaining(q.disk_gb)}{q.disk_gb && q.disk_gb.quota >= 0 ? 'GB' : ''}
											</span>
										</div>
									{:else}
										<div class="text-gray-600 text-xs flex-shrink-0">quota 없음</div>
									{/if}
								</div>
							</button>
						{/each}
					</div>
				{/if}
			{/if}
			<div class="flex justify-start mt-6 pt-4 border-t border-gray-800">
				<button
					onclick={closeWizard}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg hover:border-gray-500 transition-colors"
				>취소</button>
			</div>
		{:else if loading}
			<div class="flex items-center justify-center py-16">
				<LoadingSpinner size="lg" color="blue">데이터 로드 중...</LoadingSpinner>
			</div>
		{:else if deploying}
			<!-- 배포 진행 중 -->
			<div class="mb-6">
				<h1 class="text-xl font-bold text-white">VM 생성</h1>
				<p class="text-sm text-gray-500 mt-1">배포 진행 중</p>
			</div>
			<div class="bg-gray-900 rounded-xl border border-gray-700 p-6 mb-6">
				<h2 class="text-lg font-semibold text-white mb-4">VM 배포 진행 중</h2>
				<ProgressBar
					steps={progressSteps}
					currentStep={currentStep}
					progress={progress}
					error={deployError}
				/>
				<div class="flex items-center justify-between mt-4">
					<p class="text-gray-400 text-sm">{progressMessage}</p>
					{#if elapsedSeconds !== null}
						<p class="text-gray-600 text-xs font-mono">{elapsedSeconds.toFixed(0)}s 경과</p>
					{/if}
				</div>
			</div>
		{:else}
			<!-- 헤더 -->
			<WizardHeader
				step={$wizard.step}
				totalSteps={TOTAL_STEPS}
				stepName={stepLabels[$wizard.step - 1]}
				{adminMode}
				adminProjectName={adminSelectedProjectName}
				onReset={handleReset}
				onClose={closeWizard}
			/>

			{#if loadError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-6">
					{loadError}
				</div>
			{/if}

			<!-- 스테퍼 -->
			<WizardStepper
				cur={$wizard.step}
				totalSteps={TOTAL_STEPS}
				{stepLabels}
				{goTo}
			/>

			<!-- 단계별 내용 -->
			<div class="mb-8">
				{#if $wizard.step === 1}
					<h2 class="text-lg font-semibold text-white mb-3">부트 소스 선택</h2>
					<!-- 이미지 / 기존 볼륨 토글 -->
					<div class="flex mb-5 rounded-lg overflow-hidden border border-gray-700">
						<button
							class="flex-1 py-2 text-sm transition-colors {$wizard.bootSource === 'image' ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
							onclick={() => wizard.update(w => ({ ...w, bootSource: 'image', bootVolumeId: null, bootVolumeName: null }))}
						>OS 이미지</button>
						<button
							class="flex-1 py-2 text-sm transition-colors {$wizard.bootSource === 'volume' ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
							onclick={() => wizard.update(w => ({ ...w, bootSource: 'volume', imageId: null, imageName: null }))}
						>기존 부팅 볼륨</button>
					</div>

					{#if $wizard.bootSource === 'image'}
						<p class="text-sm text-gray-400 mb-4">Glance에 등록된 공개 이미지, 직접 업로드한 이미지는 <a href="/dashboard/compute/images" class="text-blue-400 hover:underline">이미지 페이지</a>에서 관리할 수 있습니다.</p>
						<SelectImage {images} selectedId={$wizard.imageId} onSelect={selectImage} />
					{:else}
						{@const bootableVols = volumes.filter(v => v.bootable && v.status === 'available')}
						<p class="text-sm text-gray-400 mb-4">부팅 가능하고 <span class="text-green-400">available</span> 상태인 볼륨만 표시됩니다.</p>
						{#if bootableVols.length === 0}
							<div class="text-center py-10 text-gray-600 text-sm">부팅 가능한 볼륨이 없습니다.</div>
						{:else}
							<div class="space-y-2 max-h-96 overflow-y-auto pr-1">
								{#each bootableVols as vol}
									<button
										onclick={() => wizard.update(w => ({ ...w, bootVolumeId: vol.id, bootVolumeName: vol.name }))}
										class="w-full text-left rounded-lg border px-4 py-3 transition-colors {$wizard.bootVolumeId === vol.id ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
									>
										<div class="flex items-center justify-between">
											<span class="text-sm text-white font-medium">{vol.name || vol.id.slice(0, 8)}</span>
											<span class="text-xs text-gray-500 font-mono">{vol.size} GB</span>
										</div>
										{#if vol.volume_image_metadata?.image_name}
											<div class="text-xs text-gray-500 mt-0.5">{vol.volume_image_metadata.image_name}</div>
										{/if}
									</button>
								{/each}
							</div>
						{/if}
					{/if}

				{:else if $wizard.step === 2}
					<h2 class="text-lg font-semibold text-white mb-1">플레이버 선택 <span class="text-gray-500 text-sm font-normal">VM의 vCPU / 메모리 / 디스크 스펙</span></h2>
					<SelectFlavor {flavors} selectedId={$wizard.flavorId} onSelect={selectFlavor} quota={flavorQuota} />

				{:else if $wizard.step === 3}
					<h2 class="text-lg font-semibold text-white mb-1">라이브러리 레이어 <span class="text-gray-500 text-sm font-normal">OverlayFS로 마운트할 사전 빌드 레이어</span></h2>
					{#snippet step3Tab()}
						{@const useTemplate = $wizard.templateName !== null}
						<div class="flex mb-4 rounded-lg overflow-hidden border border-gray-700">
							<button
								class="flex-1 py-2 text-sm transition-colors {!useTemplate ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
								onclick={() => wizard.update(w => ({ ...w, templateName: null, templateVersion: null }))}
							>라이브러리 선택</button>
							<button
								class="flex-1 py-2 text-sm transition-colors {useTemplate ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
								onclick={() => wizard.update(w => ({ ...w, libraries: [] }))}
							>템플릿 선택</button>
						</div>
						{#if useTemplate}
							<SelectTemplate />
						{:else}
							<SelectLibraries
								{libraries}
								selected={$wizard.libraries}
								{hasGpuFlavor}
								{ubuntuVersion}
								onToggle={toggleLibrary}
							/>
						{/if}
					{/snippet}
					{@render step3Tab()}

				{:else if $wizard.step === 4}
					<h2 class="text-lg font-semibold text-white mb-4">배포 전략 <span class="text-gray-500 text-sm font-normal">스케줄링 / 레이어 마운트</span></h2>
					<SelectStrategy
						scheduling={$wizard.scheduling}
						onSchedulingChange={selectScheduling}
						strategy={$wizard.strategy}
						hasLibraries={$wizard.libraries.length > 0}
						{hasPrebuilt}
						onStrategyChange={selectStrategy}
						mountProtocol={$wizard.mountProtocol}
						onProtocolChange={selectMountProtocol}
					/>

				{:else if $wizard.step === 5}
					<h2 class="text-lg font-semibold text-white mb-5">인스턴스 설정</h2>

					<!-- VM 이름 -->
					<div class="mb-4">
						<label for="vm-name" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
							VM 이름 <span class="text-red-400">*</span>
						</label>
						<input
							id="vm-name"
							bind:value={$wizard.instanceName}
							type="text"
							placeholder="my-vm"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
						/>
					</div>

					<!-- 네트워크 + 키페어 -->
					<div class="grid grid-cols-1 @lg/panel:grid-cols-2 gap-3.5 mb-4">
						<div>
							<label for="create-network" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
								네트워크 <span class="text-red-400">*</span>
							</label>
							<select
								id="create-network"
								value={$wizard.networkId ?? ''}
								onchange={e => selectNetwork((e.target as HTMLSelectElement).value || null)}
								class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
							>
								<option value="">기본 네트워크</option>
								{#each networks as net}
									<option value={net.id}>
										{net.name}{net.id === defaultNetworkId ? ' (기본)' : ''}{net.is_external ? ' (외부)' : ''}{net.is_shared ? ' (공유)' : ''}
									</option>
								{/each}
							</select>
						</div>
						<div>
							{#if adminMode}
								<label class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
									키페어 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
								</label>
								<div class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-500 text-sm">
									없음 (관리자 생성 — 콘솔 비밀번호 사용)
								</div>
								<p class="text-xs text-amber-400/80 mt-1">admin 모드에서는 대상 프로젝트의 키페어에 접근할 수 없습니다.</p>
							{:else}
								<label for="create-keypair" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
									키페어 <span class="text-red-400">*</span>
								</label>
								<select
									id="create-keypair"
									value={$wizard.keyName ?? ''}
									onchange={e => wizard.update(w => ({ ...w, keyName: (e.target as HTMLSelectElement).value || null }))}
									class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
								>
									<option value="">키페어 선택</option>
									{#each keypairs as kp}
										<option value={kp.name}>{kp.name}</option>
									{/each}
								</select>
								{#if keypairs.length === 0}
									<p class="text-xs text-amber-400 mt-1">등록된 키페어가 없습니다.</p>
								{/if}
							{/if}
						</div>
					</div>

					<!-- 보안 그룹 + 가용 영역 -->
					<div class="grid grid-cols-1 @lg/panel:grid-cols-2 gap-3.5 mb-4">
						<div>
							<label for="create-sg" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
								보안 그룹 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
							</label>
							<select
								id="create-sg"
								value={$wizard.securityGroups[0] ?? ''}
								onchange={e => {
									const v = (e.target as HTMLSelectElement).value;
									wizard.update(w => ({ ...w, securityGroups: v ? [v] : [] }));
								}}
								class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
							>
								<option value="">기본</option>
								{#each securityGroups as sg}
									<option value={sg.name}>{sg.name}</option>
								{/each}
							</select>
						</div>
						<div>
							<label for="create-az" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
								가용 영역 <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
							</label>
							<select
								id="create-az"
								value={$wizard.availabilityZone ?? ''}
								onchange={e => {
									const v = (e.target as HTMLSelectElement).value;
									wizard.update(w => ({ ...w, availabilityZone: v || null }));
								}}
								class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
							>
								<option value="">자동 (nova)</option>
								{#each availabilityZones as az}
									<option value={az.name}>{az.name}</option>
								{/each}
							</select>
						</div>
					</div>

					<!-- 루트 디스크 -->
					{#if $wizard.bootSource === 'image'}
					<div class="grid grid-cols-1 @lg/panel:grid-cols-2 gap-3.5 mb-4">
						<div>
							<label for="boot-volume-size" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
								루트 디스크 <span class="text-red-400">*</span>
							</label>
							<div class="flex items-center gap-3">
								<input
									id="boot-volume-size"
									bind:value={$wizard.bootVolumeSizeGb}
									type="number"
									min="1"
									max="16384"
									class="w-24 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
								/>
								<span class="text-[11px] text-gray-500">1 – 16,384 GB</span>
							</div>
						</div>
						<div class="flex items-end pb-1">
							<label class="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/60 border border-gray-700 cursor-pointer w-full">
								<input
									type="checkbox"
									bind:checked={$wizard.deleteBootVolumeOnTermination}
									class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 flex-shrink-0"
								/>
								<span class="text-sm text-gray-300">VM 삭제 시 루트 디스크 함께 삭제</span>
							</label>
						</div>
					</div>
					{:else}
					<div class="mb-4 p-3 rounded-lg bg-blue-900/20 border border-blue-800/40 text-blue-300 text-xs">
						기존 부팅 볼륨 사용 시 루트 디스크 크기 설정이 적용되지 않습니다. 볼륨: <span class="font-medium">{$wizard.bootVolumeName ?? $wizard.bootVolumeId}</span>
					</div>
					{/if}

					<!-- cloud-init 다크 에디터 -->
					<div class="mb-4">
						<label for="cloud-init" class="block text-[11.5px] font-semibold text-gray-300 tracking-tight flex items-center gap-1.5 mb-1.5">
							CLOUD-INIT <span class="text-[10px] text-gray-500 font-normal px-1.5 py-0.5 rounded-full bg-gray-800">선택</span>
						</label>
						<div class="relative">
							<div class="absolute top-2 right-2 flex gap-1 z-[2] bg-gray-900 border border-gray-700 rounded-md p-0.5">
								<button type="button" disabled class="px-2 py-1 text-[10.5px] font-mono text-gray-500 rounded opacity-50 cursor-not-allowed">예제 ▾</button>
								<button type="button" disabled class="px-2 py-1 text-[10.5px] font-mono text-gray-500 rounded opacity-50 cursor-not-allowed">YAML ✓</button>
							</div>
							<textarea
								id="cloud-init"
								bind:value={$wizard.cloudInit}
								rows="8"
								placeholder="#cloud-config&#10;package_update: true&#10;packages:&#10;  - htop"
								class="w-full p-3.5 font-mono text-xs bg-[#0f172a] text-slate-200 rounded-lg border border-gray-700 outline-none min-h-[140px] resize-y leading-relaxed focus:border-blue-500"
							></textarea>
						</div>
					</div>

				{:else if $wizard.step === 6}
					{@const reviewFlavor = flavors.find((f: any) => f.id === $wizard.flavorId)}
					{@const reviewGpu = (() => {
						if (!reviewFlavor) return '';
						const alias = reviewFlavor.extra_specs?.['pci_passthrough:alias'] ?? '';
						if (!alias) return '';
						const parts = alias.split(',').filter((e: string) => e.includes(':') && !e.toLowerCase().includes('audio'));
						return parts.map((e: string) => {
							const idx = e.lastIndexOf(':');
							return `${e.slice(0, idx).trim()} × ${parseInt(e.slice(idx + 1)) || 1}`;
						}).join(', ');
					})()}
					<h2 class="text-lg font-semibold text-white mb-4">최종 확인</h2>

					<div class="rounded-xl bg-gray-900 border border-gray-800 overflow-hidden mb-4">
						<!-- 이름 -->
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium">이름</span>
							<span class="text-sm text-white font-semibold font-mono">{$wizard.instanceName || '-'}</span>
							<button onclick={() => goTo(5)} class="review-edit-btn">✎ 수정</button>
						</div>
						<!-- 이미지 / 볼륨 -->
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium">
								{$wizard.bootSource === 'volume' ? '부트 볼륨' : '이미지'}
							</span>
							<span class="flex flex-col gap-0.5 min-w-0 text-sm text-white font-mono">
								{#if $wizard.bootSource === 'volume'}
									{$wizard.bootVolumeName ?? $wizard.bootVolumeId ?? '-'}
								{:else}
									<span class="font-semibold truncate">{$wizard.imageName ?? '-'}</span>
								{/if}
							</span>
							<button onclick={() => goTo(1)} class="review-edit-btn">✎ 수정</button>
						</div>
						<!-- 플레이버 -->
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-start px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium mt-0.5">플레이버</span>
							<span class="flex flex-col gap-2 min-w-0">
								<span class="text-sm text-white font-mono font-semibold">{$wizard.flavorName ?? '-'}</span>
								{#if reviewFlavor}
									<div class="grid grid-cols-4 gap-2">
										<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
											<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">vCPU</span>
											<span class="font-mono text-sm font-semibold text-white">{reviewFlavor.vcpus}</span>
										</div>
										<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
											<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">RAM</span>
											<span class="font-mono text-sm font-semibold text-white">{reviewFlavor.ram >= 1024 ? Math.round(reviewFlavor.ram / 1024) + 'G' : reviewFlavor.ram + 'M'}</span>
										</div>
										<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
											<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">Disk</span>
											<span class="font-mono text-sm font-semibold text-white">{reviewFlavor.disk}G</span>
										</div>
										<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
											<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">GPU</span>
											<span class="font-mono text-sm font-semibold {reviewGpu ? 'text-purple-400' : 'text-gray-600'}">{reviewGpu || '—'}</span>
										</div>
									</div>
								{/if}
							</span>
							<button onclick={() => goTo(2)} class="review-edit-btn mt-0.5">✎ 수정</button>
						</div>
						<!-- 라이브러리 -->
						{#if $wizard.libraries.length > 0}
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium">라이브러리</span>
							<span class="flex flex-wrap gap-1.5">
								{#each $wizard.libraries as lib}
									<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-900/30 border border-blue-800 text-blue-300 font-mono text-[11px]">{lib}</span>
								{/each}
							</span>
							<button onclick={() => goTo(3)} class="review-edit-btn">✎ 수정</button>
						</div>
						{/if}
						<!-- 키페어 -->
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium">키페어</span>
							<span class="text-sm text-white font-mono">{$wizard.keyName ?? '없음'}</span>
							<button onclick={() => goTo(5)} class="review-edit-btn">✎ 수정</button>
						</div>
						<!-- 전략 -->
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium">전략</span>
							<span class="text-sm text-white">
								{$wizard.scheduling === 'ha' ? 'HA 🛡' : '일반 ⚡'}
								{#if $wizard.strategy}
									· {$wizard.strategy === 'prebuilt' ? '사전 빌드' : 'cloud-init'}
								{/if}
							</span>
							<button onclick={() => goTo(4)} class="review-edit-btn">✎ 수정</button>
						</div>
						<!-- 네트워크 -->
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
							<span class="text-xs text-gray-400 font-medium">네트워크</span>
							<span class="text-sm text-white font-mono">{$wizard.networkName ?? '기본'}</span>
							<button onclick={() => goTo(5)} class="review-edit-btn">✎ 수정</button>
						</div>
						<!-- 루트 디스크 -->
						{#if $wizard.bootSource === 'image'}
						<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5">
							<span class="text-xs text-gray-400 font-medium">루트 디스크</span>
							<span class="text-sm text-white font-mono">
								{$wizard.bootVolumeSizeGb} GB
								<span class="text-gray-500 text-xs ml-1">({$wizard.deleteBootVolumeOnTermination ? 'VM 삭제 시 함께 삭제' : '보존'})</span>
							</span>
							<button onclick={() => goTo(5)} class="review-edit-btn">✎ 수정</button>
						</div>
						{/if}
					</div>

					{#if $wizard.libraries.length > 0}
						<div class="p-3 rounded-lg bg-yellow-900/20 border border-yellow-700/40 text-yellow-300 text-xs flex items-start gap-2 mb-4">
							<svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
							</svg>
							<span>OverlayFS upper 볼륨 50 GB가 함께 생성되며, 과금은 VM 실행 시점부터 시작됩니다.</span>
						</div>
					{/if}

					<!-- deploy banner -->
					<div class="flex items-center gap-3.5 px-4 py-3.5 rounded-lg bg-blue-950/30 border border-blue-900/50 mb-4">
						<div class="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
							</svg>
						</div>
						<div class="flex-1">
							<b class="block text-sm text-white font-semibold mb-0.5">배포 준비 완료</b>
							<small class="text-[11.5px] text-gray-400 leading-relaxed">
								VM 생성 클릭 시 OpenStack에 요청을 보냅니다. cloud-init은 첫 부팅 시 자동 실행됩니다.
								{#if reviewGpu} · GPU 가용성이 스케줄러에서 자동 확인됩니다.{/if}
							</small>
						</div>
					</div>

					{#if deployError}
						<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
							{deployError}
						</div>
					{/if}
				{/if}
			</div>

			<!-- 하단 네비게이션 -->
			<WizardFooter
				imageDisplay={$wizard.imageName ?? ($wizard.bootSource === 'volume' ? ($wizard.bootVolumeName ?? null) : null)}
				flavorDisplay={$wizard.flavorName}
				libCount={$wizard.libraries.length}
				step={$wizard.step}
				totalSteps={TOTAL_STEPS}
				canPrev={$wizard.step > 1}
				canNext={canNext}
				onCancel={closeWizard}
				onPrev={prevStep}
				onNext={nextStep}
				onDeploy={deploy}
			/>
		{/if}
	</div>
</SlidePanel>

<style>
  .review-edit-btn {
    font-size: 11.5px;
    color: rgb(156 163 175);
    padding: 2px 10px;
    border-radius: 6px;
    border: 1px solid rgb(55 65 81);
    transition: all 0.15s;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .review-edit-btn:hover {
    color: rgb(96 165 250);
    border-color: rgb(29 78 216 / 0.7);
    background: rgb(23 37 84 / 0.3);
  }
</style>
