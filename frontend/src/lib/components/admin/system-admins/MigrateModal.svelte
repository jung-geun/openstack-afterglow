<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface MigrateResult {
		migrated: number;
		skipped: number;
		errors: { user_id: string; reason: string }[];
	}

	let {
		adminProjectMemberCount,
		onClose,
		onMigrated,
	}: {
		adminProjectMemberCount: number;
		onClose: () => void;
		onMigrated: () => void;
	} = $props();

	let migrating = $state(false);
	let result = $state<MigrateResult | null>(null);
	let migrateError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function migrate() {
		migrating = true;
		migrateError = '';
		result = null;
		try {
			result = await api.post<MigrateResult>(
				'/api/admin/identity/system-roles/migrate-from-project',
				{},
				token,
				projectId,
			);
			onMigrated();
		} catch (e) {
			migrateError = e instanceof ApiError ? e.message : '마이그레이션 실패';
		} finally {
			migrating = false;
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
		<h2 class="text-lg font-semibold text-white mb-4">Admin Project 멤버 일괄 마이그레이션</h2>

		{#if result}
			<div class="mb-4 space-y-2">
				<div class="flex items-center gap-2 text-sm">
					<span class="text-green-400 font-semibold">{result.migrated}명</span>
					<span class="text-gray-400">system admin으로 부여 완료</span>
				</div>
				<div class="flex items-center gap-2 text-sm">
					<span class="text-gray-400 font-semibold">{result.skipped}명</span>
					<span class="text-gray-500">이미 system admin (skip)</span>
				</div>
				{#if result.errors.length > 0}
					<div class="mt-2 bg-red-900/30 border border-red-700 rounded-lg px-3 py-2 text-xs text-red-300">
						{result.errors.length}건 오류:
						{#each result.errors as e}
							<div class="mt-1">{e.user_id}: {e.reason}</div>
						{/each}
					</div>
				{/if}
			</div>
			<div class="flex justify-end">
				<button onclick={onClose} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">
					닫기
				</button>
			</div>
		{:else}
			{#if migrateError}
				<div class="mb-3 bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{migrateError}</div>
			{/if}
			<p class="text-sm text-gray-300 mb-5">
				admin project 멤버 <strong class="text-white">{adminProjectMemberCount}명</strong> 중 system admin이 아닌 사용자에게
				<strong class="text-white">system:all</strong> admin role을 일괄 부여합니다.
				이미 system admin인 멤버는 건너뜁니다.
			</p>
			<div class="flex justify-end gap-3">
				<button onclick={onClose} disabled={migrating} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">
					취소
				</button>
				<button
					onclick={migrate}
					disabled={migrating}
					class="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg disabled:opacity-30"
				>
					{migrating ? '마이그레이션 중...' : '마이그레이션 시작'}
				</button>
			</div>
		{/if}
	</div>
</div>
