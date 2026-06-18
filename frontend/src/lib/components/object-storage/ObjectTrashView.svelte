<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { api, ApiError } from '$lib/api/client';
	import { toast } from '$lib/stores/toast';
	import { formatStorage } from '$lib/utils/format';

	interface TrashObject {
		trash_key: string;
		original_name: string;
		deleted_at: number;
		bytes: number;
		content_type?: string;
	}

	let {
		containerName,
		token,
		projectId,
	}: {
		containerName: string;
		token: string | undefined;
		projectId: string | undefined;
	} = $props();

	let items = $state<TrashObject[]>([]);
	let loading = $state(true);
	let restoring = $state<string | null>(null);
	let purging = $state<string | null>(null);

	async function load() {
		loading = true;
		try {
			items = await api.get<TrashObject[]>(
				`/api/v1/object-storage/${encodeURIComponent(containerName)}/trash`,
				token,
				projectId
			);
		} catch {
			items = [];
		} finally {
			loading = false;
		}
	}

	async function restore(trashKey: string, origName: string) {
		restoring = trashKey;
		try {
			const res = await api.post<{ restored_name: string }>(
				`/api/v1/object-storage/${encodeURIComponent(containerName)}/trash/restore`,
				{ trash_key: trashKey },
				token,
				projectId
			);
			await load();
			toast.success(`"${res.restored_name}" 복구 완료`);
		} catch (e) {
			toast.error('복구 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			restoring = null;
		}
	}

	async function purge(trashKey: string, origName: string) {
		if (
			!(await confirmDialog(
				`"${origName}"을(를) 영구 삭제합니다. 이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?`
			))
		)
			return;
		purging = trashKey;
		try {
			await api.delete(
				`/api/v1/object-storage/${encodeURIComponent(containerName)}/trash/${encodeURIComponent(trashKey)}`,
				token,
				projectId
			);
			await load();
		} catch (e) {
			toast.error('영구 삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			purging = null;
		}
	}

	$effect(() => {
		if (containerName) load();
	});
</script>

<div class="mt-2">
	{#if loading}
		<div class="text-gray-500 text-xs py-8 text-center">휴지통 목록 로딩 중...</div>
	{:else if items.length === 0}
		<div class="text-gray-600 text-xs py-12 text-center">휴지통이 비어 있습니다</div>
	{:else}
		<div class="text-xs text-gray-500 mb-2">총 {items.length}개 항목 — 보관 기간 내 복구 가능</div>
		<table class="w-full text-xs">
			<thead>
				<tr class="border-b border-gray-800 text-gray-400">
					<th class="py-2 px-3 text-left font-medium">원본 파일명</th>
					<th class="py-2 px-3 text-left font-medium">삭제일</th>
					<th class="py-2 px-3 text-right font-medium">크기</th>
					<th class="py-2 px-3 text-right font-medium">액션</th>
				</tr>
			</thead>
			<tbody>
				{#each items as item (item.trash_key)}
					<tr class="border-b border-gray-800/40 hover:bg-gray-800/20 transition-colors">
						<td class="py-2 px-3 text-gray-300 font-mono truncate max-w-xs"
							title={item.original_name}>{item.original_name}</td
						>
						<td class="py-2 px-3 text-gray-400">
							{item.deleted_at
								? new Date(item.deleted_at * 1000).toLocaleDateString('ko-KR', {
										year: 'numeric',
										month: '2-digit',
										day: '2-digit',
									})
								: '—'}
						</td>
						<td class="py-2 px-3 text-gray-400 text-right"
							>{item.bytes ? formatStorage(item.bytes / 1_073_741_824) : '—'}</td
						>
						<td class="py-2 px-3 text-right">
							<div class="flex gap-1.5 justify-end">
								<button
									onclick={() => restore(item.trash_key, item.original_name)}
									disabled={restoring === item.trash_key}
									class="text-emerald-400 hover:text-emerald-300 disabled:text-gray-600 px-2 py-0.5 rounded border border-emerald-900 hover:border-emerald-700 disabled:border-gray-700 transition-colors"
								>
									{restoring === item.trash_key ? '복구 중...' : '복구'}
								</button>
								<button
									onclick={() => purge(item.trash_key, item.original_name)}
									disabled={purging === item.trash_key}
									class="text-red-400 hover:text-red-300 disabled:text-gray-600 px-2 py-0.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
								>
									{purging === item.trash_key ? '삭제 중...' : '영구 삭제'}
								</button>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="mt-2 text-xs text-gray-600">
			휴지통 항목도 스토리지 용량을 차지합니다. 필요 없는 항목은 영구 삭제하세요.
		</p>
	{/if}
</div>
