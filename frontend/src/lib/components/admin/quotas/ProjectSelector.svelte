<script lang="ts">
	import type { Project } from '$lib/types/quotas';

	let {
		projects,
		search = $bindable(''),
		selectedId = $bindable(''),
		selectedName = $bindable(''),
		onSelected,
	}: {
		projects: Project[];
		search?: string;
		selectedId?: string;
		selectedName?: string;
		onSelected: (id: string, name: string) => void;
	} = $props();

	let showDropdown = $state(false);

	const filtered = $derived(
		search
			? projects.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
			: projects
	);

	function pick(p: Project) {
		selectedId = p.id;
		selectedName = p.name;
		search = p.name;
		showDropdown = false;
		onSelected(p.id, p.name);
	}
</script>

<div class="mb-6 relative max-w-md">
	<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">프로젝트 선택</label>
	<input
		type="text"
		bind:value={search}
		onfocus={() => showDropdown = true}
		oninput={() => {
			showDropdown = true;
			if (!search) {
				selectedId = '';
				selectedName = '';
				onSelected('', '');
			}
		}}
		onblur={() => setTimeout(() => { showDropdown = false; }, 150)}
		placeholder="프로젝트 이름으로 검색..."
		class="w-full bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
	/>
	{#if showDropdown && filtered.length > 0}
		<div class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-60 overflow-y-auto">
			{#each filtered as p (p.id)}
				<button
					type="button"
					onmousedown={() => pick(p)}
					class="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors {selectedId === p.id ? 'bg-gray-700 text-white' : ''}"
				>{p.name}</button>
			{/each}
		</div>
	{/if}
	{#if selectedName}
		<div class="mt-1 text-xs text-gray-500">선택됨: <span class="text-blue-400">{selectedName}</span></div>
	{/if}
</div>
