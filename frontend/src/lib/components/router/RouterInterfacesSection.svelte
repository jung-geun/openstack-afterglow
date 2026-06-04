<script lang="ts">
	import RouterInterfaceAddForm from './RouterInterfaceAddForm.svelte';
	import { useRouterDetailController } from '$lib/stores/routerDetailController.svelte';

	const s = useRouterDetailController();
</script>

<section class="bg-gray-900 border border-gray-800 rounded-lg p-5">
	<div class="flex items-center justify-between mb-3">
		<h4 class="font-semibold text-white text-sm">인터페이스 ({s.router!.interfaces.length})</h4>
		<button
			onclick={() => s.showAddInterface = !s.showAddInterface}
			class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
		>+ 추가</button>
	</div>

	{#if s.showAddInterface}
		<RouterInterfaceAddForm />
	{/if}

	{#if s.router!.interfaces.length === 0}
		<p class="text-sm text-gray-600">연결된 인터페이스가 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each s.router!.interfaces as iface}
				<div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-3">
					<div class="text-sm">
						<div class="text-white font-medium">{iface.subnet_name || iface.subnet_id.slice(0, 12)}</div>
						<div class="text-gray-500 text-xs font-mono mt-0.5">{iface.ip_address}</div>
					</div>
					<button
						onclick={() => s.removeInterface(iface.subnet_id)}
						disabled={s.saving}
						class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
					>제거</button>
				</div>
			{/each}
		</div>
	{/if}
</section>
