<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Flavor {
		id: string;
		name: string;
		vcpus: number;
		ram: number;
		disk: number;
		is_public: boolean;
		description: string | null;
		extra_specs: Record<string, string>;
		is_gpu: boolean;
		gpu_count: number;
	}

	let {
		flavor: flavorIn,
		onChanged,
	}: {
		flavor: Flavor;
		onChanged: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let flavor = $state(flavorIn);
	$effect(() => {
		flavor = flavorIn;
	});

	let newSpecKey = $state('');
	let newSpecValue = $state('');
	let specSaving = $state(false);
	let specError = $state('');
	let editingSpecKey = $state<string | null>(null);
	let editingSpecValue = $state('');

	async function addExtraSpec() {
		if (!newSpecKey.trim()) return;
		specSaving = true;
		specError = '';
		try {
			await api.post(
				`/api/admin/flavors/${flavor.id}/extra-specs`,
				{ key: newSpecKey.trim(), value: newSpecValue.trim() },
				token,
				projectId,
			);
			flavor = {
				...flavor,
				extra_specs: { ...flavor.extra_specs, [newSpecKey.trim()]: newSpecValue.trim() },
			};
			newSpecKey = '';
			newSpecValue = '';
			onChanged();
		} catch (e: unknown) {
			specError = e instanceof ApiError ? e.message : 'extra_spec 추가 실패';
		} finally {
			specSaving = false;
		}
	}

	function startEditSpec(key: string, value: string) {
		editingSpecKey = key;
		editingSpecValue = value;
	}

	function cancelEditSpec() {
		editingSpecKey = null;
		editingSpecValue = '';
	}

	async function saveEditSpec() {
		if (!editingSpecKey) return;
		specSaving = true;
		specError = '';
		try {
			await api.post(
				`/api/admin/flavors/${flavor.id}/extra-specs`,
				{ key: editingSpecKey, value: editingSpecValue.trim() },
				token,
				projectId,
			);
			flavor = {
				...flavor,
				extra_specs: { ...flavor.extra_specs, [editingSpecKey]: editingSpecValue.trim() },
			};
			editingSpecKey = null;
			editingSpecValue = '';
			onChanged();
		} catch (e) {
			specError = e instanceof ApiError ? e.message : 'extra_spec 수정 실패';
		} finally {
			specSaving = false;
		}
	}

	async function deleteExtraSpec(key: string) {
		specError = '';
		try {
			await api.delete(
				`/api/admin/flavors/${flavor.id}/extra-specs/${encodeURIComponent(key)}`,
				token,
				projectId,
			);
			const specs = { ...flavor.extra_specs };
			delete specs[key];
			flavor = { ...flavor, extra_specs: specs };
			onChanged();
		} catch (e) {
			specError = e instanceof ApiError ? e.message : 'extra_spec 삭제 실패';
		}
	}
</script>

{#if specError}
	<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{specError}</div>
{/if}

{#if Object.keys(flavor.extra_specs).length === 0}
	<div class="text-gray-600 text-sm mb-4">등록된 속성이 없습니다</div>
{:else}
	<div class="space-y-1 mb-4">
		{#each Object.entries(flavor.extra_specs) as [k, v]}
			<div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
				{#if editingSpecKey === k}
					<div class="flex items-center gap-2">
						<span class="text-xs text-blue-300 font-mono break-all shrink-0">{k}</span>
						<span class="text-gray-500">=</span>
						<input
							bind:value={editingSpecValue}
							type="text"
							class="flex-1 min-w-0 bg-gray-800 border border-blue-500 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none"
							onkeydown={(e) => {
								if (e.key === 'Enter') saveEditSpec();
								if (e.key === 'Escape') cancelEditSpec();
							}}
						/>
						<button onclick={saveEditSpec} disabled={specSaving} class="text-green-400 hover:text-green-300 text-xs shrink-0">저장</button>
						<button onclick={cancelEditSpec} class="text-gray-400 hover:text-gray-300 text-xs shrink-0">취소</button>
					</div>
				{:else}
					<div class="flex items-center justify-between">
						<button
							class="flex-1 min-w-0 text-left cursor-pointer hover:bg-gray-800/50 rounded -mx-1 px-1 py-0.5 transition-colors"
							onclick={() => startEditSpec(k, v)}
						>
							<span class="text-xs text-blue-300 font-mono break-all">{k}</span>
							<span class="text-gray-500 mx-2">=</span>
							<span class="text-xs text-gray-300 font-mono break-all">{v}</span>
						</button>
						<button onclick={() => deleteExtraSpec(k)} class="ml-2 text-red-400 hover:text-red-300 text-xs shrink-0">삭제</button>
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<div class="text-sm text-gray-400 mb-2">속성 추가/수정</div>
<div class="space-y-2">
	<input
		bind:value={newSpecKey}
		type="text"
		placeholder="키 (예: hw:numa_nodes)"
		class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500"
	/>
	<input
		bind:value={newSpecValue}
		type="text"
		placeholder="값"
		class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500"
	/>
	<button
		onclick={addExtraSpec}
		disabled={specSaving || !newSpecKey.trim()}
		class="w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-30"
	>
		{specSaving ? '저장 중...' : '추가/수정'}
	</button>
</div>
