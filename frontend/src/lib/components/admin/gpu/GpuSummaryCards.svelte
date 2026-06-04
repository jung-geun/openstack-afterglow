<script lang="ts">
	let {
		summary,
	}: {
		summary: {
			total_hosts: number;
			total_gpus: number;
			used_gpus: number;
			available_gpus: number;
		};
	} = $props();
</script>

<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
	<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
		<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">전체 GPU</div>
		<div class="text-2xl font-bold text-white">{summary.total_gpus}</div>
		<div class="text-xs text-gray-500 mt-1">{summary.total_hosts}개 호스트</div>
	</div>
	<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
		<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">사용 중</div>
		<div class="text-2xl font-bold text-red-400">{summary.used_gpus}</div>
		<div class="text-xs text-gray-500 mt-1">{summary.total_gpus > 0 ? Math.round(summary.used_gpus / summary.total_gpus * 100) : 0}% 사용률</div>
	</div>
	<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
		<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">사용 가능</div>
		<div class="text-2xl font-bold text-green-400">{summary.available_gpus}</div>
		<div class="text-xs text-gray-500 mt-1">할당 가능</div>
	</div>
</div>
