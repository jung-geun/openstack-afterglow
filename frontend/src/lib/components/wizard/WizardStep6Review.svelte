<script lang="ts">
	import { wizard } from '$lib/stores/wizard';
	import { useVmCreate } from '$lib/stores/vmCreateStore.svelte';

	const s = useVmCreate();
	const reviewFlavor = $derived(s.flavors.find((f: any) => f.id === $wizard.flavorId));
	const reviewGpu = $derived.by(() => {
		if (!reviewFlavor) return '';
		const alias = reviewFlavor.extra_specs?.['pci_passthrough:alias'] ?? '';
		if (!alias) return '';
		const parts = alias.split(',').filter((e: string) => e.includes(':') && !e.toLowerCase().includes('audio'));
		return parts.map((e: string) => {
			const idx = e.lastIndexOf(':');
			return `${e.slice(0, idx).trim()} × ${parseInt(e.slice(idx + 1)) || 1}`;
		}).join(', ');
	});
</script>

<h2 class="text-lg font-semibold text-white mb-4">최종 확인</h2>

<div class="rounded-xl bg-gray-900 border border-gray-800 overflow-hidden mb-4">
	<!-- 이름 -->
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium">이름</span>
		<span class="text-sm text-white font-semibold font-mono">{$wizard.instanceName || '-'}</span>
		<button onclick={() => s.goTo(5)} class="review-edit-btn">✎ 수정</button>
	</div>
	<!-- 이미지 / 볼륨 -->
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium">
			{$wizard.bootSource === 'volume' ? '부트 볼륨' : '이미지'}
		</span>
		<span class="flex flex-col gap-0.5 min-w-0 text-sm text-white font-mono">
			{#if $wizard.bootSource === 'volume'}
				{$wizard.bootVolumeName ?? $wizard.bootVolumeId ?? '-'}
			{:else}
				<span class="font-semibold truncate">{$wizard.imageName ?? '-'}</span>
			{/if}
		</span>
		<button onclick={() => s.goTo(1)} class="review-edit-btn">✎ 수정</button>
	</div>
	<!-- 플레이버 -->
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-start px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium mt-0.5">플레이버</span>
		<span class="flex flex-col gap-2 min-w-0">
			<span class="text-sm text-white font-mono font-semibold">{$wizard.flavorName ?? '-'}</span>
			{#if reviewFlavor}
				<div class="grid grid-cols-4 gap-2">
					<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
						<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">vCPU</span>
						<span class="font-mono text-sm font-semibold text-white">{reviewFlavor.vcpus}</span>
					</div>
					<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
						<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">RAM</span>
						<span class="font-mono text-sm font-semibold text-white">{reviewFlavor.ram >= 1024 ? Math.round(reviewFlavor.ram / 1024) + 'G' : reviewFlavor.ram + 'M'}</span>
					</div>
					<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
						<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">Disk</span>
						<span class="font-mono text-sm font-semibold text-white">{reviewFlavor.disk}G</span>
					</div>
					<div class="flex flex-col gap-0.5 px-2.5 py-2 rounded-md bg-gray-800/70 border border-gray-700">
						<span class="text-[9.5px] uppercase tracking-wider text-gray-500 font-mono font-bold">GPU</span>
						<span class="font-mono text-sm font-semibold {reviewGpu ? 'text-purple-400' : 'text-gray-600'}">{reviewGpu || '—'}</span>
					</div>
				</div>
			{/if}
		</span>
		<button onclick={() => s.goTo(2)} class="review-edit-btn mt-0.5">✎ 수정</button>
	</div>
	<!-- 라이브러리 -->
	{#if $wizard.libraries.length > 0}
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium">라이브러리</span>
		<span class="flex flex-wrap gap-1.5">
			{#each $wizard.libraries as lib}
				<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-900/30 border border-blue-800 text-blue-300 font-mono text-[11px]">{lib}</span>
			{/each}
		</span>
		<button onclick={() => s.goTo(3)} class="review-edit-btn">✎ 수정</button>
	</div>
	{/if}
	<!-- 키페어 -->
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium">키페어</span>
		<span class="text-sm text-white font-mono">{$wizard.keyName ?? '없음'}</span>
		<button onclick={() => s.goTo(5)} class="review-edit-btn">✎ 수정</button>
	</div>
	<!-- 전략 -->
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium">전략</span>
		<span class="text-sm text-white">
			{$wizard.scheduling === 'ha' ? 'HA 🛡' : '일반 ⚡'}
			{#if $wizard.strategy}
				· {$wizard.strategy === 'prebuilt' ? '사전 빌드' : 'cloud-init'}
			{/if}
		</span>
		<button onclick={() => s.goTo(4)} class="review-edit-btn">✎ 수정</button>
	</div>
	<!-- 네트워크 -->
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5 border-b border-gray-800">
		<span class="text-xs text-gray-400 font-medium">네트워크</span>
		<span class="text-sm text-white font-mono">{$wizard.networkName ?? '기본'}</span>
		<button onclick={() => s.goTo(5)} class="review-edit-btn">✎ 수정</button>
	</div>
	<!-- 루트 디스크 -->
	{#if $wizard.bootSource === 'image'}
	<div class="grid grid-cols-[140px_1fr_auto] gap-4 items-center px-4 py-3.5">
		<span class="text-xs text-gray-400 font-medium">루트 디스크</span>
		<span class="text-sm text-white font-mono">
			{$wizard.bootVolumeSizeGb} GB
			<span class="text-gray-500 text-xs ml-1">({$wizard.deleteBootVolumeOnTermination ? 'VM 삭제 시 함께 삭제' : '보존'})</span>
		</span>
		<button onclick={() => s.goTo(5)} class="review-edit-btn">✎ 수정</button>
	</div>
	{/if}
</div>

{#if $wizard.libraries.length > 0}
	<div class="p-3 rounded-lg bg-yellow-900/20 border border-yellow-700/40 text-yellow-300 text-xs flex items-start gap-2 mb-4">
		<svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
		</svg>
		<span>OverlayFS upper 볼륨 50 GB가 함께 생성되며, 과금은 VM 실행 시점부터 시작됩니다.</span>
	</div>
{/if}

<!-- deploy banner -->
<div class="flex items-center gap-3.5 px-4 py-3.5 rounded-lg bg-blue-950/30 border border-blue-900/50 mb-4">
	<div class="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
		</svg>
	</div>
	<div class="flex-1">
		<b class="block text-sm text-white font-semibold mb-0.5">배포 준비 완료</b>
		<small class="text-[11.5px] text-gray-400 leading-relaxed">
			VM 생성 클릭 시 OpenStack에 요청을 보냅니다. cloud-init은 첫 부팅 시 자동 실행됩니다.
			{#if reviewGpu} · GPU 가용성이 스케줄러에서 자동 확인됩니다.{/if}
		</small>
	</div>
</div>

{#if s.deployError}
	<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
		{s.deployError}
	</div>
{/if}

<style>
  .review-edit-btn {
    font-size: 11.5px;
    color: rgb(156 163 175);
    padding: 2px 10px;
    border-radius: 6px;
    border: 1px solid rgb(55 65 81);
    transition: all 0.15s;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .review-edit-btn:hover {
    color: rgb(96 165 250);
    border-color: rgb(29 78 216 / 0.7);
    background: rgb(23 37 84 / 0.3);
  }
</style>
