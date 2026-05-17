<script lang="ts">
	import type { Volume } from '$lib/types/resources';

	interface Snapshot {
		id: string;
		name: string;
		status: string;
		volume_id: string;
		size: number;
		description: string;
		created_at: string | null;
	}
	interface QuotaItem { limit: number; in_use: number; }
	interface VolumeQuotas { storage: { volumes: QuotaItem; gigabytes: QuotaItem; }; }

	let {
		volumes,
		snapshots,
		quotas,
	}: {
		volumes: Volume[];
		snapshots: Snapshot[];
		quotas: VolumeQuotas | null;
	} = $props();

	let totalGb = $derived(volumes.reduce((s, v) => s + v.size, 0));
	let attachedCount = $derived(volumes.filter((v) => v.attachments.length > 0).length);
	let recentSnapshots = $derived(
		snapshots.filter((s) => {
			if (!s.created_at) return false;
			return Date.now() - new Date(s.created_at).getTime() < 86400000;
		}),
	);
</script>

<div class="grid grid-cols-3 gap-3.5 mb-5">
	<!-- 총 할당 용량 -->
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
		<div class="text-[11px] uppercase tracking-wider text-gray-500 font-medium mb-2">총 할당 용량</div>
		<div class="text-[26px] font-bold text-white leading-none mb-1">
			{totalGb}
			{#if quotas?.storage.gigabytes.limit && quotas.storage.gigabytes.limit > 0}
				<span class="text-[14px] font-normal text-gray-400">/ {quotas.storage.gigabytes.limit} GB</span>
			{:else}
				<span class="text-[14px] font-normal text-gray-400">GB</span>
			{/if}
		</div>
		<div class="text-[11px] text-gray-500 mb-3">
			{#if quotas?.storage.gigabytes.limit && quotas.storage.gigabytes.limit > 0}
				사용률 {Math.round(totalGb / quotas.storage.gigabytes.limit * 100)}%
			{:else}
				&nbsp;
			{/if}
		</div>
		<div class="h-1.5 bg-gray-800 rounded-full overflow-hidden">
			{#if quotas?.storage.gigabytes.limit && quotas.storage.gigabytes.limit > 0}
				{@const vpct = totalGb / quotas.storage.gigabytes.limit * 100}
				<div class="h-full rounded-full transition-all" style="width: {Math.min(100, Math.round(vpct))}%; background: {vpct >= 95 ? 'var(--gradient-usage-danger)' : vpct >= 80 ? 'var(--gradient-usage-warning)' : 'var(--gradient-usage)'}"></div>
			{/if}
		</div>
	</div>
	<!-- 볼륨 개수 -->
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
		<div class="text-[11px] uppercase tracking-wider text-gray-500 font-medium mb-2">볼륨</div>
		<div class="text-[26px] font-bold text-white leading-none mb-1">
			{volumes.length}
			{#if quotas?.storage.volumes.limit && quotas.storage.volumes.limit > 0}
				<span class="text-[14px] font-normal text-gray-400">/ {quotas.storage.volumes.limit}</span>
			{/if}
		</div>
		<div class="text-[11px] text-gray-500 mb-3">
			{#if quotas?.storage.volumes.limit && quotas.storage.volumes.limit > 0}
				사용률 {Math.round(volumes.length / quotas.storage.volumes.limit * 100)}%
			{:else}
				&nbsp;
			{/if}
		</div>
		<div class="h-1.5 bg-gray-800 rounded-full overflow-hidden">
			{#if quotas?.storage.volumes.limit && quotas.storage.volumes.limit > 0}
				{@const cpct = volumes.length / quotas.storage.volumes.limit * 100}
				<div class="h-full rounded-full transition-all" style="width: {Math.min(100, Math.round(cpct))}%; background: {cpct >= 95 ? 'var(--gradient-usage-danger)' : cpct >= 80 ? 'var(--gradient-usage-warning)' : 'var(--gradient-usage)'}"></div>
			{/if}
		</div>
		<div class="text-[11px] text-gray-500 mt-2">연결됨 {attachedCount}개</div>
	</div>
	<!-- 스냅샷 -->
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
		<div class="text-[11px] uppercase tracking-wider text-gray-500 font-medium mb-2">스냅샷</div>
		<div class="text-[26px] font-bold text-white leading-none mb-1">{snapshots.length}</div>
		<div class="text-[11px] text-gray-500">최근 24시간 {recentSnapshots.length}개</div>
	</div>
</div>
