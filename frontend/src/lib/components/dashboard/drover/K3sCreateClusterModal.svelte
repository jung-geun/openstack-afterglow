<script lang="ts">
	import { api } from '$lib/api/client';
	import type { K3sFlavor, K3sNetwork, K3sKeypair, K3sClusterTemplate } from '$lib/types/k3s';

	let {
		open = $bindable(false),
		token,
		projectId,
		createError = '',
		creating = false,
		onCreate,
	}: {
		open?: boolean;
		token?: string;
		projectId?: string;
		createError?: string;
		creating?: boolean;
		onCreate: (form: {
			name: string;
			agent_count: number;
			agent_flavor_id: string;
			network_id: string;
			key_name: string;
			os_type: string;
			template_id?: string;
		}) => void;
	} = $props();

	let form = $state({ name: '', agent_count: 1, agent_flavor_id: '', network_id: '', key_name: '', os_type: 'ubuntu', template_id: '' });
	let networkCategory = $state<'tenant' | 'provider'>('tenant');
	let flavors = $state<K3sFlavor[]>([]);
	let networks = $state<K3sNetwork[]>([]);
	let keypairs = $state<K3sKeypair[]>([]);
	let templates = $state<K3sClusterTemplate[]>([]);

	$effect(() => {
		if (open) {
			form = { name: '', agent_count: 1, agent_flavor_id: '', network_id: '', key_name: '', os_type: 'ubuntu', template_id: '' };
			networkCategory = 'tenant';
			void loadDeps();
		}
	});

	async function loadDeps() {
		try {
			[flavors, networks, keypairs, templates] = await Promise.all([
				api.get<K3sFlavor[]>('/api/flavors', token, projectId),
				api.get<K3sNetwork[]>('/api/networks', token, projectId),
				api.get<K3sKeypair[]>('/api/keypairs', token, projectId),
				api.get<K3sClusterTemplate[]>('/api/k3s/cluster-templates', token, projectId).catch(() => []),
			]);
			const defaultNet = networks.find(n => !n.is_external && (n.name === 'Default' || n.name === 'default'));
			if (defaultNet) form.network_id = defaultNet.id;
		} catch {
			flavors = []; networks = []; keypairs = [];
		}
	}

	function applyTemplate(templateId: string) {
		form.template_id = templateId;
		const tmpl = templates.find(t => t.id === templateId);
		if (!tmpl) return;
		if (tmpl.default_node_count !== undefined) form.agent_count = tmpl.default_node_count;
		if (tmpl.default_agent_flavor_id) form.agent_flavor_id = tmpl.default_agent_flavor_id;
		if (tmpl.os_type) form.os_type = tmpl.os_type;
	}

	function categoryChange(c: 'tenant' | 'provider') {
		networkCategory = c;
		form.network_id = '';
	}
</script>

{#if open}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { open = false; }}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">Drover 클러스터 생성</h2>
			<div class="space-y-4">
				{#if templates.length > 0}
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">템플릿 (선택)
						<select
							value={form.template_id}
							onchange={(e) => applyTemplate((e.target as HTMLSelectElement).value)}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5"
						>
							<option value="">템플릿 없이 직접 설정</option>
							{#each templates as t}
								<option value={t.id}>{t.name}{t.description ? ` — ${t.description}` : ''}</option>
							{/each}
						</select>
					</label>
				</div>
				{/if}
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">클러스터 이름
						<input bind:value={form.name} type="text" placeholder="미입력 시 자동 생성"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
					</label>
				</div>
				<div>
					<span class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS 타입</span>
					<div class="flex gap-2 mt-1.5">
						<button type="button"
							onclick={() => form.os_type = 'ubuntu'}
							class="flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors {form.os_type === 'ubuntu' ? 'border-blue-500 bg-blue-900/30 text-white' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}">
							<span class="text-base">🐧</span>
							<div class="text-left">
								<div class="font-medium leading-none">Ubuntu</div>
								<div class="text-xs text-gray-500 mt-0.5">cloud-init</div>
							</div>
						</button>
						<button type="button"
							onclick={() => form.os_type = 'fcos'}
							class="flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors {form.os_type === 'fcos' ? 'border-orange-500 bg-orange-900/30 text-white' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}">
							<span class="text-base">🔴</span>
							<div class="text-left">
								<div class="font-medium leading-none">CoreOS</div>
								<div class="text-xs text-gray-500 mt-0.5">Ignition</div>
							</div>
						</button>
					</div>
					{#if form.os_type === 'fcos'}
						<div class="mt-2 text-xs text-orange-400/80 bg-orange-900/10 border border-orange-800/40 rounded px-2.5 py-1.5">
							서버의 <code class="font-mono">k3s.fcos_image_id</code> 설정이 필요합니다.
						</div>
					{/if}
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">에이전트 수 (0-10)
						<input bind:value={form.agent_count} type="number" min="0" max="10"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">에이전트 플레이버 (선택)
						<select bind:value={form.agent_flavor_id}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
							<option value="">기본값 사용</option>
							{#each flavors as f}
								<option value={f.id}>{f.name} ({f.vcpus}vCPU / {Math.round(f.ram/1024)}GB)</option>
							{/each}
						</select>
					</label>
				</div>
				<div>
					<div class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">네트워크</div>
					<div class="flex gap-2 mb-2">
						<button type="button"
							onclick={() => categoryChange('tenant')}
							class="flex-1 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors {networkCategory === 'tenant' ? 'border-blue-500 bg-blue-900/30 text-blue-300' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}">
							Tenant
						</button>
						<button type="button"
							onclick={() => categoryChange('provider')}
							class="flex-1 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors {networkCategory === 'provider' ? 'border-orange-500 bg-orange-900/30 text-orange-300' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}">
							Provider
						</button>
					</div>
					<select bind:value={form.network_id}
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
						<option value="">{networkCategory === 'tenant' ? '기본값 사용' : '선택 안 함'}</option>
						{#each networks.filter(n => networkCategory === 'provider' ? n.is_external : !n.is_external) as n}
							<option value={n.id}>{n.name || n.id.slice(0,12)}</option>
						{/each}
					</select>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">키페어 (선택)
						<select bind:value={form.key_name}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
							<option value="">없음</option>
							{#each keypairs as kp}
								<option value={kp.name}>{kp.name}</option>
							{/each}
						</select>
					</label>
				</div>
			</div>
			{#if createError}
				<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>
			{/if}
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => open = false}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
				<button onclick={() => { open = false; onCreate({...form, template_id: form.template_id || undefined}); }} disabled={creating}
					class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
					생성
				</button>
			</div>
		</div>
	</div>
{/if}
