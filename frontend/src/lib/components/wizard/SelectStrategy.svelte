<script lang="ts">
	let { selected, hasPrebuilt, mountProtocol, onSelect, onProtocolChange }: {
		selected: 'prebuilt' | 'dynamic' | null;
		hasPrebuilt: boolean;
		mountProtocol: 'CEPHFS' | 'NFS';
		onSelect: (s: 'prebuilt' | 'dynamic') => void;
		onProtocolChange: (p: 'CEPHFS' | 'NFS') => void;
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

{#if selected === 'dynamic'}
	<div class="mt-4 p-4 rounded-xl border border-gray-700 bg-gray-900">
		<div class="text-xs text-gray-400 uppercase tracking-wide mb-3">마운트 프로토콜</div>
		<div class="flex gap-3">
			<button
				onclick={() => onProtocolChange('NFS')}
				class="flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-all {mountProtocol === 'NFS' ? 'border-blue-500 bg-blue-900/20 text-blue-300' : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500'}"
			>NFS</button>
			<button
				onclick={() => onProtocolChange('CEPHFS')}
				class="flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-all {mountProtocol === 'CEPHFS' ? 'border-purple-500 bg-purple-900/20 text-purple-300' : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500'}"
			>CephFS</button>
		</div>
		<p class="text-xs text-gray-500 mt-2">
			{#if mountProtocol === 'NFS'}
				NFS: 범용 파일 시스템 프로토콜. 대부분 환경에서 사용 가능합니다.
			{:else}
				CephFS: Ceph 네이티브 프로토콜. 높은 성능과 안정성을 제공합니다.
			{/if}
		</p>
	</div>
{/if}
