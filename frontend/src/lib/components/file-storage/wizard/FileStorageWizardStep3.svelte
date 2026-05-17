<script lang="ts">
	import { useFsWizard } from '$lib/stores/fileStorageWizardStore.svelte';

	const s = useFsWizard();
</script>

<div class="flex items-center gap-2 mb-4">
	<span class="w-5 h-5 rounded-full bg-green-900/50 border border-green-600 flex items-center justify-center text-green-400 text-xs">✓</span>
	<h2 class="text-base font-semibold text-white">"{s.createdFs!.name}" 생성 완료</h2>
</div>

{#if s.createdFs!.export_locations && s.createdFs!.export_locations.length > 0}
	<div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 mb-4">
		<p class="text-xs text-gray-500 mb-1">Export Location (마운트 경로)</p>
		<div class="flex items-center gap-2">
			<code class="text-xs text-green-300 font-mono flex-1 truncate">{s.createdFs!.export_locations[0]}</code>
			<button onclick={() => s.copyExport(s.createdFs!.export_locations[0], s.createdFs!.id)}
				class="shrink-0 text-gray-500 hover:text-gray-300 text-xs px-2 py-1 rounded border border-gray-700 transition-colors">
				{s.copiedExport === s.createdFs!.id ? '복사됨' : '복사'}
			</button>
		</div>
	</div>
{/if}

<div class="mb-4">
	<p class="text-xs text-gray-400 uppercase tracking-wide mb-3">접근 규칙 추가</p>
	<div class="flex gap-2 items-end">
		<div class="flex-1">
			<label class="block text-xs text-gray-500 mb-1">
				{s.createdFs!.share_proto === 'NFS' ? 'IP / CIDR' : 'CephX ID'}
				<input bind:value={s.ruleForm.access_to} type="text"
					placeholder={s.createdFs!.share_proto === 'NFS' ? '예: 192.168.1.0/24' : '예: my-client'}
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1 font-mono" />
			</label>
		</div>
		<div>
			<label class="block text-xs text-gray-500 mb-1">권한
				<select bind:value={s.ruleForm.access_level}
					class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1">
					<option value="rw">읽기/쓰기</option>
					<option value="ro">읽기 전용</option>
				</select>
			</label>
		</div>
		<button onclick={s.addAccessRule} disabled={s.addingRule || !s.ruleForm.access_to.trim()}
			class="px-4 py-2 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm rounded-lg transition-colors whitespace-nowrap mb-[1px]">
			{s.addingRule ? '추가 중...' : '+ 추가'}
		</button>
	</div>
	{#if s.ruleError}<div class="mt-2 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{s.ruleError}</div>{/if}
</div>

{#if s.accessRules.length > 0}
	<div class="border border-gray-700 rounded-lg overflow-hidden mb-4">
		<table class="w-full text-xs">
			<thead>
				<tr class="border-b border-gray-700 text-gray-500 uppercase tracking-wide bg-gray-800/50">
					<th class="text-left px-3 py-2">{s.createdFs!.share_proto === 'NFS' ? 'IP/CIDR' : 'CephX ID'}</th>
					<th class="text-left px-3 py-2">권한</th>
					<th class="text-left px-3 py-2">상태</th>
					{#if s.createdFs!.share_proto !== 'NFS'}<th class="text-left px-3 py-2">Access Key</th>{/if}
				</tr>
			</thead>
			<tbody>
				{#each s.accessRules as rule (rule.id)}
					<tr class="border-b border-gray-800 last:border-0">
						<td class="px-3 py-2 font-mono text-gray-300">{rule.access_to}</td>
						<td class="px-3 py-2">
							<span class="px-1.5 py-0.5 rounded {rule.access_level === 'rw' ? 'bg-blue-900/30 text-blue-300' : 'bg-gray-800 text-gray-400'}">{rule.access_level}</span>
						</td>
						<td class="px-3 py-2 text-gray-500">{rule.state}</td>
						{#if s.createdFs!.share_proto !== 'NFS'}
							<td class="px-3 py-2">
								{#if rule.access_key}
									<div class="flex items-center gap-1.5">
										<code class="text-gray-400 font-mono truncate max-w-[120px]">{rule.access_key.slice(0, 12)}…</code>
										<button onclick={() => s.copyKey(rule.access_key!, rule.id)}
											class="text-gray-600 hover:text-gray-300 transition-colors">
											{s.copiedKey === rule.id ? '✓' : '⎘'}
										</button>
									</div>
								{:else}
									<span class="text-gray-600">대기 중</span>
								{/if}
							</td>
						{/if}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{:else}
	<p class="text-xs text-gray-600 mb-4">아직 추가된 접근 규칙이 없습니다.</p>
{/if}

<div class="flex justify-end gap-3 mt-2">
	<button onclick={s.closeWizard} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">건너뛰기</button>
	<button onclick={s.closeWizard} class="px-5 py-2 bg-green-700 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors">완료</button>
</div>
