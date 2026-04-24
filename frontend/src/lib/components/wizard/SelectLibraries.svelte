<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';

	interface LibraryConfig {
		id: string;
		name: string;
		version: string;
		depends_on: string[];
		available_prebuilt: boolean;
		share_proto: string;
	}

	let { libraries, selected, hasGpuFlavor, ubuntuVersion, onToggle }: {
		libraries: LibraryConfig[];
		selected: string[];
		hasGpuFlavor: boolean;
		ubuntuVersion?: string;
		onToggle: (id: string, deps: string[]) => void;
	} = $props();

	let warnings = $state<string[]>([]);
	let validateTimer: ReturnType<typeof setTimeout> | null = null;

	function isSelected(id: string) {
		return selected.includes(id);
	}

	function isRequiredBy(id: string): boolean {
		// 다른 선택된 라이브러리가 이것에 의존하는 경우 해제 불가
		return libraries.some(
			(lib) => isSelected(lib.id) && lib.depends_on.includes(id) && lib.id !== id
		);
	}

	// 선택 변경 시 호환성 검증 (debounce 300ms)
	$effect(() => {
		const ids = [...selected]; // 반응형 구독
		if (validateTimer) clearTimeout(validateTimer);
		if (ids.length === 0) {
			warnings = [];
			return;
		}
		validateTimer = setTimeout(async () => {
			try {
				const token = $auth.token ?? undefined;
				const projectId = $auth.projectId ?? undefined;
				const body: Record<string, unknown> = { library_ids: ids };
				if (ubuntuVersion) body.ubuntu_version = ubuntuVersion;
				const res = await api.post<{ compatible: boolean; messages: string[] }>(
					'/api/libraries/validate', body, token, projectId
				);
				warnings = res.messages ?? [];
			} catch {
				warnings = [];
			}
		}, 300);
	});
</script>

<div class="space-y-3">
	{#if warnings.length > 0}
		<div class="p-3 rounded-lg border border-yellow-700 bg-yellow-900/20 text-yellow-300 text-xs space-y-1">
			{#each warnings as w}
				<div>⚠️ {w}</div>
			{/each}
		</div>
	{/if}
	{#each libraries as lib}
		{@const selected_ = isSelected(lib.id)}
		{@const locked = isRequiredBy(lib.id)}
		{@const gpuWarn = lib.id === 'vllm' && !hasGpuFlavor}

		<div class="flex items-start gap-3 p-4 rounded-xl border transition-all {selected_
				? 'border-blue-500 bg-blue-900/10'
				: 'border-gray-700 bg-gray-900'}">
			<input
				type="checkbox"
				id={lib.id}
				checked={selected_}
				disabled={locked}
				onchange={() => onToggle(lib.id, lib.depends_on)}
				class="mt-0.5 accent-blue-500"
			/>
			<label for={lib.id} class="flex-1 cursor-pointer {locked ? 'opacity-60' : ''}">
				<div class="flex items-center gap-2 mb-0.5">
					<span class="font-medium text-white text-sm">{lib.name}</span>
					<span class="text-gray-500 text-xs">v{lib.version}</span>
					{#if lib.available_prebuilt}
						<span class="px-1.5 py-0.5 bg-green-900/40 text-green-400 rounded text-xs">사전 빌드 가능</span>
					{/if}
					{#if lib.share_proto}
						<span class="px-1.5 py-0.5 rounded text-xs {lib.share_proto === 'NFS' ? 'bg-blue-900/40 text-blue-400' : 'bg-purple-900/40 text-purple-400'}">{lib.share_proto}</span>
					{/if}
				</div>
				{#if lib.depends_on.length > 0}
					<div class="text-xs text-gray-500">
						필요: {lib.depends_on.join(', ')}
						{#if locked}<span class="text-orange-400 ml-1">(다른 라이브러리가 의존 중)</span>{/if}
					</div>
				{/if}
				{#if gpuWarn}
					<div class="text-xs text-yellow-400 mt-1">
						⚠️ GPU 플레이버를 선택해야 vLLM이 정상 동작합니다
					</div>
				{/if}
			</label>
		</div>
	{/each}
</div>
