<script lang="ts">
	import { useDbInstanceDetailController } from '$lib/stores/dbInstanceDetailController.svelte';

	const s = useDbInstanceDetailController();

	let showBackupForm = $state(false);
	let newBackup = $state({ name: '', description: '' });

	// 자동 백업 설정 폼 상태
	let autoForm = $state({ max_daily: 2, max_weekly: 2, max_monthly: 1 });
	let showAutoForm = $state(false);

	// 자동 백업 활성화 여부
	const autoEnabled = $derived(s.autoBackupConfig !== null);

	// 자동 백업 폼 열 때 현재 설정값으로 초기화
	function openAutoForm() {
		if (s.autoBackupConfig) {
			autoForm = {
				max_daily: s.autoBackupConfig.max_daily,
				max_weekly: s.autoBackupConfig.max_weekly,
				max_monthly: s.autoBackupConfig.max_monthly,
			};
		} else {
			autoForm = { max_daily: 2, max_weekly: 2, max_monthly: 1 };
		}
		showAutoForm = true;
	}

	async function handleToggleAutoBackup() {
		if (autoEnabled) {
			await s.disableAutoBackup();
		} else {
			openAutoForm();
		}
	}

	async function handleSaveAutoBackup() {
		await s.saveAutoBackupConfig(autoForm.max_daily, autoForm.max_weekly, autoForm.max_monthly);
		showAutoForm = false;
	}

	async function handleCreateBackup() {
		if (!newBackup.name.trim()) return;
		const ok = await s.createBackup(newBackup.name.trim(), newBackup.description);
		if (ok) {
			showBackupForm = false;
			newBackup = { name: '', description: '' };
		}
	}
</script>

<!-- 자동 백업 설정 -->
<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-3">
	<div class="flex items-center justify-between">
		<div>
			<h2 class="text-sm font-semibold text-white">자동 백업</h2>
			{#if autoEnabled}
				<p class="text-xs text-gray-500 mt-0.5">
					일 {s.autoBackupConfig!.max_daily}개 · 주 {s.autoBackupConfig!.max_weekly}개 · 월 {s.autoBackupConfig!.max_monthly}개 보존
				</p>
			{:else}
				<p class="text-xs text-gray-600 mt-0.5">비활성화됨</p>
			{/if}
		</div>
		<div class="flex items-center gap-2">
			{#if autoEnabled}
				<button onclick={openAutoForm}
					class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
					설정 변경
				</button>
			{/if}
			<button
				onclick={handleToggleAutoBackup}
				disabled={s.savingAutoBackup}
				title={autoEnabled ? '자동 백업 비활성화' : '자동 백업 활성화'}
				class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out disabled:opacity-50 {autoEnabled ? 'bg-blue-600' : 'bg-gray-700'}"
			>
				<span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {autoEnabled ? 'translate-x-4' : 'translate-x-0'}"></span>
			</button>
		</div>
	</div>

	{#if showAutoForm}
		<div class="mt-3 bg-gray-800 rounded-lg p-3 space-y-3">
			<p class="text-xs text-gray-400">보존 개수 (0 = 해당 주기 비사용)</p>
			<div class="grid grid-cols-3 gap-3">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">일별 최대</span>
					<input type="number" min="0" max="30" bind:value={autoForm.max_daily}
						class="bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 text-center" />
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">주별 최대</span>
					<input type="number" min="0" max="30" bind:value={autoForm.max_weekly}
						class="bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 text-center" />
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">월별 최대</span>
					<input type="number" min="0" max="12" bind:value={autoForm.max_monthly}
						class="bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 text-center" />
				</label>
			</div>
			<div class="flex gap-2">
				<button onclick={handleSaveAutoBackup} disabled={s.savingAutoBackup}
					class="text-xs bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
					{s.savingAutoBackup ? '저장 중...' : '저장'}
				</button>
				<button onclick={() => { showAutoForm = false; }}
					class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-3 py-1.5 rounded transition-colors">
					취소
				</button>
			</div>
		</div>
	{/if}
</div>

<!-- 수동 백업 -->
<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<div class="flex items-center justify-between mb-3">
		<h2 class="text-sm font-semibold text-white">백업</h2>
		<button onclick={() => { showBackupForm = !showBackupForm; s.backupError = ''; }}
			class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
			{showBackupForm ? '취소' : '+ 백업 생성'}
		</button>
	</div>
	{#if showBackupForm}
		<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
			<input type="text" bind:value={newBackup.name} placeholder="backup-name"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			<input type="text" bind:value={newBackup.description} placeholder="설명 (선택)"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			{#if s.backupError}<p class="text-red-400 text-xs">{s.backupError}</p>{/if}
			<button onclick={handleCreateBackup} disabled={s.creatingBackup || !newBackup.name.trim()}
				class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
				{s.creatingBackup ? '생성 중...' : '백업 생성'}
			</button>
		</div>
	{/if}
	{#if s.backups.length === 0}
		<div class="text-gray-600 text-xs">백업이 없습니다</div>
	{:else}
		<table class="w-full text-sm">
			<thead>
				<tr class="text-gray-500 text-xs">
					<th class="text-left py-2 font-medium">이름</th>
					<th class="text-left py-2 font-medium">상태</th>
					<th class="text-left py-2 font-medium">크기</th>
					<th class="text-left py-2 font-medium">생성일</th>
					<th class="text-right py-2 font-medium">액션</th>
				</tr>
			</thead>
			<tbody>
				{#each s.backups as b}
					<tr class="border-t border-gray-800/50">
						<td class="py-2 text-white">{b.name}</td>
						<td class="py-2 text-gray-400 text-xs">{b.status}</td>
						<td class="py-2 text-gray-400 text-xs">{b.size ? `${b.size} GB` : '-'}</td>
						<td class="py-2 text-gray-500 text-xs">{b.created_at ? b.created_at.slice(0, 10) : '-'}</td>
						<td class="py-2 text-right">
							<div class="flex justify-end gap-1">
								<button onclick={() => s.restoreBackup(b.id)} disabled={s.restoringBackup === b.id}
									class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-blue-900 hover:border-blue-700 transition-colors">
									{s.restoringBackup === b.id ? '...' : '복원'}
								</button>
								<button onclick={() => s.deleteBackup(b.id)} disabled={s.deletingBackup === b.id}
									class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
									{s.deletingBackup === b.id ? '...' : '삭제'}
								</button>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>
