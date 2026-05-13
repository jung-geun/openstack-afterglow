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

<div class="flex flex-col gap-3">
	<!-- 일반 배포 (prebuilt) -->
	<button
		onclick={() => onSelect('prebuilt')}
		class="flex items-start gap-3 p-4 rounded-xl border text-left transition-all {selected === 'prebuilt'
			? 'border-blue-500 bg-blue-900/15 ring-1 ring-blue-500/30'
			: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
	>
		<div class="w-5 h-5 rounded-md flex-shrink-0 mt-0.5 flex items-center justify-center border transition-colors
			{selected === 'prebuilt' ? 'bg-blue-500 border-blue-500' : 'border-gray-600 bg-gray-800'}">
			{#if selected === 'prebuilt'}
				<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
				</svg>
			{/if}
		</div>
		<div class="flex-1 flex flex-col gap-1.5">
			<div class="flex items-center gap-2.5 flex-wrap">
				<b class="text-sm font-semibold text-white">일반 배포</b>
				<span class="ml-auto text-gray-500 font-mono text-[11.5px]">⚡ ~30초 부팅</span>
			</div>
			<p class="text-xs text-gray-400 leading-relaxed">단일 VM, 호스트 고정 배치. 재시작이 없고 부팅이 빠릅니다.</p>
		</div>
	</button>

	<!-- HA 배포 (dynamic) -->
	<button
		onclick={() => onSelect('dynamic')}
		class="flex items-start gap-3 p-4 rounded-xl border text-left transition-all {selected === 'dynamic'
			? 'border-blue-500 bg-blue-900/15 ring-1 ring-blue-500/30'
			: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
	>
		<div class="w-5 h-5 rounded-md flex-shrink-0 mt-0.5 flex items-center justify-center border transition-colors
			{selected === 'dynamic' ? 'bg-blue-500 border-blue-500' : 'border-gray-600 bg-gray-800'}">
			{#if selected === 'dynamic'}
				<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
				</svg>
			{/if}
		</div>
		<div class="flex-1 flex flex-col gap-1.5">
			<div class="flex items-center gap-2.5 flex-wrap">
				<b class="text-sm font-semibold text-white">HA 배포</b>
				<span class="px-1.5 py-0.5 rounded bg-blue-900/30 border border-blue-800 text-blue-400 text-[11px] font-mono">권장</span>
				<span class="ml-auto text-gray-500 font-mono text-[11.5px]">⏱ ~3-5분 부팅</span>
			</div>
			<p class="text-xs text-gray-400 leading-relaxed">호스트 장애 시 자동 마이그레이션. 클라우드 init 초기화가 추가됩니다.</p>
		</div>
	</button>
</div>
