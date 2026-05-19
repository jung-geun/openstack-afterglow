<script lang="ts">
	import type { Instance } from '$lib/types/compute';
	import ActionMenu from '$lib/components/ui/ActionMenu.svelte';

	let {
		instance,
		onAction,
	}: {
		instance: Instance;
		onAction: (kind: 'console' | 'shelve' | 'unshelve' | 'delete', instance: Instance) => Promise<void>;
	} = $props();

	let open = $state(false);
	let acting = $state(false);

	async function act(kind: 'console' | 'shelve' | 'unshelve' | 'delete') {
		open = false;
		acting = true;
		await onAction(kind, instance);
		acting = false;
	}
</script>

<div class="hidden sm:flex items-center justify-end" role="none">
	<ActionMenu
		{open}
		onopen={() => { open = true; }}
		onclose={() => { open = false; }}
	>
		{#if instance.status === 'ACTIVE'}
			<button onclick={() => act('console')} class="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800 hover:text-white transition-colors">콘솔</button>
		{/if}
		{#if instance.status === 'ACTIVE' || instance.status === 'SHUTOFF'}
			<button onclick={() => act('shelve')} class="w-full text-left px-3 py-1.5 text-xs text-purple-400 hover:bg-gray-800 hover:text-purple-300 transition-colors">보관</button>
		{/if}
		{#if instance.status === 'SHELVED_OFFLOADED' || instance.status === 'SHELVED'}
			<button onclick={() => act('unshelve')} class="w-full text-left px-3 py-1.5 text-xs text-green-400 hover:bg-gray-800 hover:text-green-300 transition-colors">해제</button>
		{/if}
		<button onclick={() => act('delete')} disabled={acting} class="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-gray-800 hover:text-red-300 disabled:text-gray-600 transition-colors">
			{acting ? '처리 중...' : '삭제'}
		</button>
	</ActionMenu>
</div>
