<script lang="ts">
	import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';
	import type { PodInfo } from '$lib/types/k3s';

	interface Props {
		pod: PodInfo;
		onClose: () => void;
	}

	let { pod, onClose }: Props = $props();

	const s = useK3sClusterDetailController();

	let container = $state<string | undefined>(pod.containers[0]?.name);
	let tailLines = $state(200);
	let log = $state('');
	let loading = $state(false);
	let error = $state('');

	async function fetchLog() {
		loading = true;
		error = '';
		const result = await s.fetchPodLog(pod.name, { container, tailLines });
		if (result) {
			log = result.log;
		} else {
			error = '로그 조회 실패';
		}
		loading = false;
	}

	$effect(() => {
		void [container, tailLines];
		fetchLog();
	});
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
	onclick={onClose}
	role="dialog"
	aria-modal="true"
>
	<div
		class="bg-gray-950 border border-gray-700 rounded-2xl w-[90vw] max-w-4xl max-h-[85vh] flex flex-col shadow-2xl"
		onclick={(e) => e.stopPropagation()}
		role="none"
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-5 py-3 border-b border-gray-800">
			<div>
				<span class="text-sm font-semibold text-white">{pod.name}</span>
				<span class="ml-2 text-xs text-gray-400">로그</span>
			</div>
			<div class="flex items-center gap-3">
				{#if pod.containers.length > 1}
					<select
						bind:value={container}
						class="text-xs bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-2 py-1"
					>
						{#each pod.containers as c}
							<option value={c.name}>{c.name}</option>
						{/each}
					</select>
				{/if}
				<select
					bind:value={tailLines}
					class="text-xs bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-2 py-1"
				>
					<option value={50}>마지막 50줄</option>
					<option value={200}>마지막 200줄</option>
					<option value={1000}>마지막 1000줄</option>
				</select>
				<button
					onclick={fetchLog}
					disabled={loading}
					class="text-xs px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors disabled:opacity-40"
				>새로고침</button>
				<button
					onclick={onClose}
					class="text-gray-400 hover:text-white transition-colors text-lg leading-none"
				>✕</button>
			</div>
		</div>

		<!-- Log body -->
		<div class="flex-1 overflow-auto p-4">
			{#if loading}
				<div class="text-gray-400 text-sm text-center py-8">로딩 중...</div>
			{:else if error}
				<div class="text-red-400 text-sm">{error}</div>
			{:else if !log}
				<div class="text-gray-500 text-sm text-center py-8">로그 없음</div>
			{:else}
				<pre class="text-xs text-gray-200 font-mono whitespace-pre-wrap break-words leading-relaxed">{log}</pre>
			{/if}
		</div>
	</div>
</div>
