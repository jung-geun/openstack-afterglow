<script lang="ts">
	import DetailHeader from '$lib/components/ui/DetailHeader.svelte';
	import { useRouterDetail } from '$lib/stores/routerDetail.svelte';

	const s = useRouterDetail();
</script>

<DetailHeader
	title={s.router!.name || s.router!.id.slice(0, 12)}
	subtitle={s.router!.id}
	status={s.router!.status}
>
	{#snippet actions()}
		<button
			onclick={() => s.deleteRouter()}
			disabled={s.saving}
			class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
		>삭제</button>
	{/snippet}
</DetailHeader>
