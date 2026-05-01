<script lang="ts">
	import ProfileSection from '$lib/components/account/ProfileSection.svelte';
	import PasswordSection from '$lib/components/account/PasswordSection.svelte';

	let { open = $bindable(false), onclose }: { open?: boolean; onclose?: () => void } = $props();

	function close() {
		onclose?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
<div class="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:items-center sm:pt-0">
	<!-- backdrop -->
	<button
		class="absolute inset-0 bg-black/60"
		onclick={close}
		aria-label="닫기"
		tabindex="-1"
	></button>

	<!-- panel -->
	<div class="relative bg-gray-950 border border-gray-800 rounded-2xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto shadow-2xl">
		<!-- 헤더 -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-800 sticky top-0 bg-gray-950 z-10">
			<h2 class="text-lg font-bold text-white">계정 설정</h2>
			<div class="flex items-center gap-3">
				<a href="/dashboard/account" onclick={close} class="text-xs text-blue-400 hover:text-blue-300 transition-colors">전체 설정 →</a>
				<button onclick={close} class="text-gray-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-gray-800">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
					</svg>
				</button>
			</div>
		</div>

		<div class="p-6 space-y-4">
			<ProfileSection />
			<PasswordSection />
		</div>
	</div>
</div>
{/if}
