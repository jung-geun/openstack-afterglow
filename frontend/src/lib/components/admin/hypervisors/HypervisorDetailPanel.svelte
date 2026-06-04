<script lang="ts">
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';

	export interface HypervisorDetail {
		id: string;
		hypervisor_hostname: string;
		state: string;
		status: string;
		hypervisor_type: string;
		hypervisor_version: number;
		host_ip: string;
		host_time: string;
		uptime: string;
		service_host: string;
		vcpus: number;
		vcpus_used: number;
		vcpus_allowed: number;
		memory_mb: number;
		memory_mb_used: number;
		memory_allowed_mb: number;
		local_gb: number;
		local_gb_used: number;
		running_vms: number;
		cpu_info: string | null;
		servers: { id: string; name: string; status: string; project_id: string; flavor: string }[];
	}

	let {
		detail,
		loading,
		projectNameMap,
		onClose,
		onMigrate,
	}: {
		detail: HypervisorDetail | null;
		loading: boolean;
		projectNameMap: Map<string, string>;
		onClose: () => void;
		onMigrate: (serverId: string, serverName: string, type: 'live' | 'cold') => void;
	} = $props();
</script>

<div class="w-96 border-l border-gray-800 bg-gray-950 flex flex-col overflow-hidden flex-shrink-0">
	<div class="flex items-center justify-between px-4 py-3 border-b border-gray-800">
		<h2 class="text-sm font-semibold text-white truncate">{detail?.hypervisor_hostname ?? '로딩 중...'}</h2>
		<button onclick={onClose} class="text-gray-400 hover:text-white text-lg leading-none">×</button>
	</div>

	{#if loading}
		<div class="p-4"><LoadingSkeleton variant="table" rows={4} /></div>
	{:else if detail}
		<div class="flex-1 overflow-y-auto p-4 space-y-4">
			<!-- 기본 정보 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
				<dl class="space-y-2 text-xs">
					<div class="flex justify-between">
						<dt class="text-gray-400">상태</dt>
						<dd class="{detail.state === 'up' && detail.status === 'enabled' ? 'text-green-400' : 'text-red-400'}">{detail.state}/{detail.status}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">호스트 IP</dt>
						<dd class="text-gray-300 font-mono">{detail.host_ip || '-'}</dd>
					</div>
					{#if detail.host_time}
					<div class="flex justify-between">
						<dt class="text-gray-400">호스트 시간</dt>
						<dd class="text-gray-300 font-mono">{detail.host_time}</dd>
					</div>
					{/if}
					{#if detail.uptime}
					<div class="flex justify-between gap-4">
						<dt class="text-gray-400 flex-shrink-0">업타임</dt>
						<dd class="text-gray-300 text-right text-xs leading-relaxed break-all">{detail.uptime}</dd>
					</div>
					{/if}
					<div class="flex justify-between">
						<dt class="text-gray-400">타입</dt>
						<dd class="text-gray-300">{detail.hypervisor_type}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">버전</dt>
						<dd class="text-gray-300">{detail.hypervisor_version}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">서비스 호스트</dt>
						<dd class="text-gray-300 font-mono">{detail.service_host || '-'}</dd>
					</div>
				</dl>
			</div>

			<!-- 리소스 현황 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">리소스 현황</h3>
				<dl class="space-y-2 text-xs">
					<div class="flex justify-between">
						<dt class="text-gray-400">vCPU</dt>
						<dd class="text-gray-300">{detail.vcpus_used} / {detail.vcpus_allowed || detail.vcpus} <span class="text-gray-600 text-xs">(물리 {detail.vcpus})</span></dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">RAM</dt>
						<dd class="text-gray-300">{formatNumber(Math.round(detail.memory_mb_used/1024))} / {formatNumber(Math.round((detail.memory_allowed_mb || detail.memory_mb)/1024))} GB <span class="text-gray-600 text-xs">(물리 {formatNumber(Math.round(detail.memory_mb/1024))} GB)</span></dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">로컬 디스크</dt>
						<dd class="text-gray-300">{formatStorage(detail.local_gb_used)} / {formatStorage(detail.local_gb)}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">실행 중 VM</dt>
						<dd class="text-gray-300">{detail.running_vms}</dd>
					</div>
				</dl>
			</div>

			<!-- VM 목록 -->
			{#if detail.servers.length > 0}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">VM 목록 ({detail.servers.length})</h3>
					<div class="space-y-1.5">
						{#each detail.servers as s}
							<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50 last:border-0">
								<div class="flex-1 min-w-0">
									<div class="text-xs text-gray-300 truncate">{s.name || s.id.slice(0, 12)}</div>
									<div class="text-xs text-gray-500">{projectNameMap.get(s.project_id) || s.project_id.slice(0, 8)} · {s.flavor}</div>
								</div>
								<div class="flex items-center gap-1 ml-2 flex-shrink-0">
									<span class="text-xs {s.status === 'ACTIVE' ? 'text-green-400' : s.status === 'ERROR' ? 'text-red-400' : 'text-gray-400'}">{s.status}</span>
									{#if s.status === 'ACTIVE'}
										<button onclick={() => onMigrate(s.id, s.name, 'live')} class="px-1.5 py-0.5 text-xs bg-cyan-900/30 hover:bg-cyan-900/60 text-cyan-400 rounded">이동</button>
									{:else if s.status === 'SHUTOFF'}
										<button onclick={() => onMigrate(s.id, s.name, 'cold')} class="px-1.5 py-0.5 text-xs bg-teal-900/30 hover:bg-teal-900/60 text-teal-400 rounded">이동</button>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
