<script lang="ts">
	export interface NotionTargetForm {
		label: string;
		apiKey: string;
		databaseId: string;
		enabled: boolean;
		intervalMinutes: number;
		usersDatabaseId: string;
		hypervisorsDatabaseId: string;
		gpuSpecDatabaseId: string;
	}

	let {
		form,
		mode,
	}: {
		form: NotionTargetForm;
		mode: 'add' | 'edit';
	} = $props();

	const inputClass = 'w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500';
	const monoInputClass = inputClass + ' font-mono';
</script>

<div class="space-y-3">
	<div>
		<label class="block text-xs text-gray-400 mb-1">레이블 (식별용)</label>
		<input bind:value={form.label} type="text" placeholder="예: 운영팀 DB" class={inputClass} />
	</div>
	<div>
		<label class="block text-xs text-gray-400 mb-1">
			Notion API Key
			{#if mode === 'add'}
				<span class="text-red-400">*</span>
			{:else}
				<span class="text-gray-600">(변경 시에만 입력)</span>
			{/if}
		</label>
		<input
			bind:value={form.apiKey}
			type="password"
			placeholder={mode === 'add' ? 'ntn_...' : '변경하지 않으면 비워두세요'}
			class={monoInputClass}
		/>
	</div>
	<div>
		<label class="block text-xs text-gray-400 mb-1">
			인스턴스 Database ID
			{#if mode === 'add'}<span class="text-red-400">*</span>{/if}
		</label>
		<input bind:value={form.databaseId} type="text" placeholder="32자리 UUID" class={monoInputClass} />
	</div>
	<div class="grid grid-cols-2 gap-3">
		<div>
			<label class="block text-xs text-gray-400 mb-1">사용자 DB ID <span class="text-gray-600">(선택)</span></label>
			<input bind:value={form.usersDatabaseId} type="text" placeholder="People DB" class={monoInputClass} />
		</div>
		<div>
			<label class="block text-xs text-gray-400 mb-1">하이퍼바이저 DB ID <span class="text-gray-600">(선택)</span></label>
			<input bind:value={form.hypervisorsDatabaseId} type="text" placeholder="Hypervisor DB" class={monoInputClass} />
		</div>
	</div>
	<div>
		<label class="block text-xs text-gray-400 mb-1">GPU Spec DB ID <span class="text-gray-600">(선택)</span></label>
		<input bind:value={form.gpuSpecDatabaseId} type="text" placeholder="GPU Spec DB" class={monoInputClass} />
	</div>
	<div class="flex gap-4 items-end">
		<div>
			<label class="block text-xs text-gray-400 mb-1">동기화 간격 (분)</label>
			<input bind:value={form.intervalMinutes} type="number" min="1" max="1440"
				class="w-24 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
		</div>
		<label class="flex items-center gap-2 cursor-pointer pb-2">
			<input bind:checked={form.enabled} type="checkbox"
				class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500" />
			<span class="text-sm text-gray-300">활성화</span>
		</label>
	</div>
</div>
