<script lang="ts">
	import { api, ApiError } from '$lib/api/client';
	import type { K3sFlavor, K3sNodegroup } from '$lib/types/k3s';

	let {
		clusterId,
		token,
		projectId,
		onClose,
		onSaved,
	}: {
		clusterId: string;
		token?: string;
		projectId?: string;
		onClose: () => void;
		onSaved: (ng: K3sNodegroup) => void;
	} = $props();

	let form = $state({
		name: '',
		role: 'agent',
		node_count: 0,
		flavor_id: '',
	});
	let flavors = $state<K3sFlavor[]>([]);
	let saving = $state(false);
	let error = $state('');

	$effect(() => {
		void api.get<K3sFlavor[]>('/api/flavors', token, projectId).then(f => { flavors = f; }).catch(() => {});
	});

	async function save() {
		saving = true;
		error = '';
		try {
			const body = {
				name: form.name,
				role: form.role,
				node_count: Number(form.node_count),
				flavor_id: form.flavor_id || null,
			};
			const ng = await api.post<K3sNodegroup>(
				`/api/k3s/clusters/${clusterId}/nodegroups`,
				body,
				token,
				projectId,
			);
			onSaved(ng);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			saving = false;
		}
	}
</script>

<div
	class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
	role="dialog"
	tabindex="-1"
>
	<div
		class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	>
		<h2 class="text-lg font-semibold text-white mb-5">노드그룹 추가</h2>

		<div class="space-y-4">
			<label class="block text-xs text-gray-400 uppercase tracking-wide">
				이름
				<input
					bind:value={form.name}
					type="text"
					placeholder="gpu-workers"
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5"
				/>
			</label>

			<div>
				<span class="block text-xs text-gray-400 uppercase tracking-wide mb-1.5">역할</span>
				<div class="flex gap-2">
					<button
						type="button"
						onclick={() => (form.role = 'agent')}
						class="flex-1 px-3 py-2 rounded-lg border text-sm transition-colors {form.role === 'agent' ? 'border-blue-500 bg-blue-900/30 text-white' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}"
					>에이전트</button>
					<button
						type="button"
						onclick={() => (form.role = 'server')}
						class="flex-1 px-3 py-2 rounded-lg border text-sm transition-colors {form.role === 'server' ? 'border-purple-500 bg-purple-900/30 text-white' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}"
					>서버</button>
				</div>
			</div>

			<label class="block text-xs text-gray-400 uppercase tracking-wide">
				노드 수 (0–20)
				<input
					bind:value={form.node_count}
					type="number"
					min="0"
					max="20"
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5"
				/>
			</label>

			<label class="block text-xs text-gray-400 uppercase tracking-wide">
				Flavor (선택)
				<select
					bind:value={form.flavor_id}
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5"
				>
					<option value="">기본값 사용</option>
					{#each flavors as f}
						<option value={f.id}>{f.name} ({f.vcpus}vCPU / {Math.round(f.ram / 1024)}GB)</option>
					{/each}
				</select>
			</label>
		</div>

		{#if error}
			<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>
		{/if}

		<div class="flex justify-end gap-3 mt-6">
			<button onclick={onClose} disabled={saving} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
			<button
				onclick={save}
				disabled={saving || !form.name}
				class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg"
			>
				{saving ? '생성 중...' : '생성'}
			</button>
		</div>
	</div>
</div>
