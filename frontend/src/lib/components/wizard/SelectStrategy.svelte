<script lang="ts">
	let { selected, hasPrebuilt, onSelect }: {
		selected: 'prebuilt' | 'dynamic' | null;
		hasPrebuilt: boolean;
		onSelect: (s: 'prebuilt' | 'dynamic') => void;
	} = $props();
</script>

<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
	<!-- Strategy A: 사전 빌드 -->
	<button
		onclick={() => onSelect('prebuilt')}
		disabled={!hasPrebuilt}
		class="text-left p-5 rounded-xl border transition-all {selected === 'prebuilt'
			? 'border-blue-500 bg-blue-900/20'
			: 'border-gray-700 bg-gray-900 hover:border-gray-500'} {!hasPrebuilt ? 'opacity-50 cursor-not-allowed' : ''}"
	>
		<div class="flex items-center justify-between mb-3">
			<span class="font-semibold text-white">Strategy A</span>
			<span class="px-2 py-0.5 bg-green-900/40 text-green-400 rounded text-xs">빠름</span>
		</div>
		<div class="text-sm text-gray-300 font-medium mb-2">사전 빌드 파일 스토리지</div>
		<ul class="text-xs text-gray-500 space-y-1">
			<li>✓ 빠른 부팅 (설치 불필요)</li>
			<li>✓ 여러 VM이 파일 스토리지 공유 (효율적)</li>
			<li>✓ read-only 격리로 안전</li>
			<li class="text-gray-600">✗ 버전 고정 (관리자 빌드 필요)</li>
		</ul>
		{#if !hasPrebuilt}
			<div class="mt-3 text-xs text-orange-400">관리자가 사전 빌드 파일 스토리지를 아직 생성하지 않았습니다</div>
		{/if}
	</button>

	<!-- Strategy B: 동적 생성 -->
	<button
		onclick={() => onSelect('dynamic')}
		class="text-left p-5 rounded-xl border transition-all {selected === 'dynamic'
			? 'border-blue-500 bg-blue-900/20'
			: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
	>
		<div class="flex items-center justify-between mb-3">
			<span class="font-semibold text-white">Strategy B</span>
			<span class="px-2 py-0.5 bg-yellow-900/40 text-yellow-400 rounded text-xs">유연</span>
		</div>
		<div class="text-sm text-gray-300 font-medium mb-2">동적 생성 (VM 전용 파일 스토리지)</div>
		<ul class="text-xs text-gray-500 space-y-1">
			<li>✓ 항상 최신 버전</li>
			<li>✓ 커스텀 설정 가능</li>
			<li>✓ VM 전용 쓰기 가능 레이어</li>
			<li class="text-gray-600">✗ 첫 부팅 느림 (pip install)</li>
		</ul>
	</button>
</div>
