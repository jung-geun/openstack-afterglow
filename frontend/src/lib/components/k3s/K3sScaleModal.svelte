<script lang="ts">
	interface Props {
		deploymentName: string;
		currentReplicas: number;
		onClose: () => void;
		onApply: (replicas: number) => Promise<void>;
	}

	let { deploymentName, currentReplicas, onClose, onApply }: Props = $props();

	let replicas = $state(currentReplicas);
	let applying = $state(false);

	async function handleApply() {
		applying = true;
		try {
			await onApply(replicas);
			onClose();
		} finally {
			applying = false;
		}
	}
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onclick={onClose} role="dialog" aria-modal="true">
	<div class="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-80 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none">
		<h3 class="text-sm font-semibold text-white mb-1">Deployment 스케일</h3>
		<p class="text-xs text-gray-400 mb-4 font-mono">{deploymentName}</p>

		<div class="flex items-center justify-center gap-4 mb-6">
			<button
				onclick={() => { replicas = Math.max(0, replicas - 1); }}
				class="w-9 h-9 rounded-lg bg-gray-800 text-white text-lg hover:bg-gray-700 transition-colors disabled:opacity-40"
				disabled={replicas <= 0}
			>−</button>
			<span class="text-2xl font-bold text-white tabular-nums w-12 text-center">{replicas}</span>
			<button
				onclick={() => { replicas = Math.min(100, replicas + 1); }}
				class="w-9 h-9 rounded-lg bg-gray-800 text-white text-lg hover:bg-gray-700 transition-colors disabled:opacity-40"
				disabled={replicas >= 100}
			>+</button>
		</div>

		<div class="flex gap-2">
			<button
				onclick={onClose}
				class="flex-1 py-2 rounded-lg text-xs text-gray-400 bg-gray-800 hover:bg-gray-700 transition-colors"
			>취소</button>
			<button
				onclick={handleApply}
				disabled={applying || replicas === currentReplicas}
				class="flex-1 py-2 rounded-lg text-xs text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-40 transition-colors"
			>{applying ? '적용 중...' : '적용'}</button>
		</div>
	</div>
</div>
