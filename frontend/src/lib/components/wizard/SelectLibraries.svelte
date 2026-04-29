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
		size_bytes?: number;
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
		return libraries.some(
			(lib) => isSelected(lib.id) && lib.depends_on.includes(id) && lib.id !== id
		);
	}

	function formatSize(bytes?: number): string {
		if (!bytes) return '';
		const gb = bytes / (1024 * 1024 * 1024);
		return gb >= 1 ? `${Math.round(gb)} GB` : `${Math.round(gb * 1024)} MB`;
	}

	$effect(() => {
		const ids = [...selected];
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

<p class="text-sm text-gray-400 mb-4">
	선택한 레이어는 첫 부팅 시 cloud-init으로 자동 마운트됩니다.
</p>

{#if warnings.length > 0}
	<div class="p-3 rounded-lg border border-yellow-700 bg-yellow-900/20 text-yellow-300 text-xs space-y-1 mb-4">
		{#each warnings as w}
			<div>⚠ {w}</div>
		{/each}
	</div>
{/if}

<div class="space-y-2">
	{#each libraries as lib}
		{@const selected_ = isSelected(lib.id)}
		{@const locked = isRequiredBy(lib.id)}
		{@const gpuWarn = lib.id === 'vllm' && !hasGpuFlavor}

		<button
			type="button"
			onclick={() => { if (!locked) onToggle(lib.id, lib.depends_on); }}
			disabled={locked}
			class="w-full text-left flex items-center gap-3 p-4 rounded-xl border transition-all {selected_
				? 'border-blue-500 bg-blue-900/10'
				: 'border-gray-700 bg-gray-900 hover:border-gray-500'} {locked ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}"
		>
			<!-- 체크박스 -->
			<div class="w-5 h-5 rounded flex-shrink-0 flex items-center justify-center border transition-colors
				{selected_ ? 'bg-blue-500 border-blue-500' : 'border-gray-600 bg-gray-800'}">
				{#if selected_}
					<svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
					</svg>
				{/if}
			</div>

			<!-- 이름 + 의존성 -->
			<div class="flex-1 min-w-0">
				<div class="flex items-center gap-2">
					<span class="font-medium text-white text-sm">{lib.name}</span>
				</div>
				{#if lib.depends_on.length > 0}
					<div class="text-xs text-gray-500 mt-0.5">
						↳ requires {lib.depends_on.join(', ')}
						{#if locked}<span class="text-orange-400 ml-1">(의존 중)</span>{/if}
					</div>
				{/if}
				{#if gpuWarn}
					<div class="text-xs text-yellow-400 mt-1">GPU 플레이버 필요</div>
				{/if}
			</div>

			<!-- 크기 -->
			{#if lib.size_bytes}
				<span class="text-xs text-gray-500 flex-shrink-0">{formatSize(lib.size_bytes)}</span>
			{/if}
		</button>
	{/each}
</div>
