<script lang="ts">
	import { formatRam } from '$lib/utils/quotaFormat';
	import type { Quotas } from '$lib/types/quotas';

	let {
		quotas,
		saving,
		saveError,
		saveSuccess,
		onSave,
	}: {
		quotas: Quotas;
		saving: boolean;
		saveError: string;
		saveSuccess: string;
		onSave: (form: { instances: number; cores: number; ram: number; volumes: number; gigabytes: number }) => void;
	} = $props();

	let form = $state({ instances: 0, cores: 0, ram: 0, volumes: 0, gigabytes: 0 });

	$effect(() => {
		form = {
			instances: quotas?.compute?.instances?.limit ?? 0,
			cores: quotas?.compute?.cores?.limit ?? 0,
			ram: quotas?.compute?.ram?.limit ?? 0,
			volumes: quotas?.volume?.volumes?.limit ?? 0,
			gigabytes: quotas?.volume?.gigabytes?.limit ?? 0,
		};
	});
</script>

{#if saveSuccess}<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{saveSuccess}</div>{/if}
{#if saveError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{saveError}</div>{/if}

<!-- Compute Quotas -->
<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
	<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Compute 쿼터</h2>
	<div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
		<div>
			<label class="block text-xs text-gray-400 mb-1.5">인스턴스</label>
			<div class="text-sm text-gray-500 mb-1">사용: {quotas?.compute?.instances?.in_use ?? 0}</div>
			<input bind:value={form.instances} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
		</div>
		<div>
			<label class="block text-xs text-gray-400 mb-1.5">CPU 코어</label>
			<div class="text-sm text-gray-500 mb-1">사용: {quotas?.compute?.cores?.in_use ?? 0}</div>
			<input bind:value={form.cores} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
		</div>
		<div>
			<label class="block text-xs text-gray-400 mb-1.5">RAM (MB)</label>
			<div class="text-sm text-gray-500 mb-1">사용: {formatRam(quotas?.compute?.ram?.in_use ?? 0)}</div>
			<input bind:value={form.ram} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
		</div>
	</div>
</div>

<!-- Volume Quotas -->
<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
	<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Volume 쿼터</h2>
	<div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
		<div>
			<label class="block text-xs text-gray-400 mb-1.5">볼륨</label>
			<div class="text-sm text-gray-500 mb-1">사용: {quotas?.volume?.volumes?.in_use ?? 0}</div>
			<input bind:value={form.volumes} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
		</div>
		<div>
			<label class="block text-xs text-gray-400 mb-1.5">용량 (GB)</label>
			<div class="text-sm text-gray-500 mb-1">사용: {quotas?.volume?.gigabytes?.in_use ?? 0} GB</div>
			<input bind:value={form.gigabytes} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
		</div>
	</div>
</div>

<div class="flex justify-end mb-6">
	<button onclick={() => onSave(form)} disabled={saving} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">
		{saving ? '저장 중...' : '저장'}
	</button>
</div>
