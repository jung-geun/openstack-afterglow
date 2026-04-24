<script lang="ts">
	let { selected, hasPrebuilt, mountProtocol, onSelect, onProtocolChange }: {
		selected: 'prebuilt' | 'dynamic' | null;
		hasPrebuilt: boolean;
		mountProtocol: 'CEPHFS' | 'NFS';
		onSelect: (s: 'prebuilt' | 'dynamic') => void;
		onProtocolChange: (p: 'CEPHFS' | 'NFS') => void;
	} = $props();
</script>

<p class="text-sm text-gray-400 mb-5">VM의 실패 대비 동작과 가용 영역을 지정하세요.</p>

<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
	<!-- 일반 배포 (prebuilt) -->
	<button
		onclick={() => onSelect('prebuilt')}
		class="relative text-left p-5 rounded-xl border transition-all {selected === 'prebuilt'
			? 'border-blue-500 bg-blue-900/15 ring-1 ring-blue-500/30'
			: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
	>
		{#if selected === 'prebuilt'}
			<div class="absolute top-3 right-3 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
				<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
				</svg>
			</div>
		{/if}
		<div class="flex items-center gap-3 mb-3">
			<div class="w-10 h-10 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center">
				<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
				</svg>
			</div>
			<span class="font-semibold text-white text-sm">일반 배포</span>
		</div>
		<p class="text-xs text-gray-500">단일 VM, 재시작 없음</p>
	</button>

	<!-- HA 배포 (dynamic) -->
	<button
		onclick={() => onSelect('dynamic')}
		class="relative text-left p-5 rounded-xl border transition-all {selected === 'dynamic'
			? 'border-blue-500 bg-blue-900/15 ring-1 ring-blue-500/30'
			: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
	>
		{#if selected === 'dynamic'}
			<div class="absolute top-3 right-3 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
				<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
				</svg>
			</div>
		{/if}
		<div class="flex items-center gap-3 mb-3">
			<div class="w-10 h-10 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center">
				<svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
				</svg>
			</div>
			<div class="flex items-center gap-2">
				<span class="font-semibold text-white text-sm">HA 배포</span>
				<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-[10px] border border-blue-700/40">권장</span>
			</div>
		</div>
		<p class="text-xs text-gray-500">호스트 장애 시 자동 마이그레이션</p>
	</button>
</div>
