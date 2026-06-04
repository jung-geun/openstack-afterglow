<script lang="ts">
	import type { GpuQuota } from '$lib/types/quotas';

	let {
		rows,
		defaults,
		loading,
		error,
		hasAnyAlias,
		onSetLimit,
		onClear,
	}: {
		rows: GpuQuota[];
		defaults: Record<string, number>;
		loading: boolean;
		error: string;
		hasAnyAlias: boolean;
		onSetLimit: (alias: string, limit: number) => void;
		onClear: (alias: string) => void;
	} = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
	<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-1">GPU Quota</h2>
	<p class="text-xs text-gray-600 mb-4">이 프로젝트의 GPU quota입니다. 개별 설정이 없으면 전체 기본값이 적용됩니다.</p>
	{#if error}<div class="text-red-400 text-xs mb-3">{error}</div>{/if}
	{#if loading}
		<div class="text-gray-500 text-sm">불러오는 중...</div>
	{:else if rows.length === 0 && !hasAnyAlias}
		<div class="text-gray-600 text-sm">GPU alias를 찾을 수 없습니다.</div>
	{:else}
		<table class="w-full text-sm">
			<thead>
				<tr class="text-gray-400 text-xs border-b border-gray-800">
					<th class="text-left pb-2">GPU 타입</th>
					<th class="text-right pb-2">기본값</th>
					<th class="text-right pb-2">프로젝트 Limit</th>
					<th class="text-right pb-2">사용 중</th>
					<th class="text-right pb-2">가용</th>
					<th class="text-right pb-2"></th>
				</tr>
			</thead>
			<tbody>
				{#each rows as q}
					{@const alias = q.gpu_type}
					{@const defLimit = defaults[alias] ?? 0}
					{@const effectiveLimit = q.limit}
					{@const inUse = q.in_use}
					{@const avail = effectiveLimit === -1 ? -1 : effectiveLimit - inUse}
					<tr class="border-b border-gray-800/50 last:border-0">
						<td class="py-2 text-white font-mono">{alias}</td>
						<td class="py-2 text-right text-gray-500">{defLimit === -1 ? '무제한' : defLimit}</td>
						<td class="py-2 text-right">
							<input
								type="number"
								min="-1"
								value={q?.limit ?? ''}
								placeholder={String(defLimit)}
								onchange={(e) => {
									const v = (e.target as HTMLInputElement).value;
									if (v === '') {
										onClear(alias);
									} else {
										onSetLimit(alias, Number(v));
									}
								}}
								class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white text-right focus:outline-none focus:border-blue-500"
							/>
						</td>
						<td class="py-2 text-right text-gray-400">{inUse}</td>
						<td class="py-2 text-right {avail > 0 ? 'text-green-400' : avail === -1 ? 'text-gray-500' : 'text-red-400'}">
							{effectiveLimit === -1 ? '무제한' : avail}
						</td>
						<td class="py-2 text-right">
							{#if q?.limit != null}
								<button
									onclick={() => onClear(alias)}
									class="text-xs text-gray-500 hover:text-gray-300 transition-colors"
									title="프로젝트별 설정 삭제 (기본값으로 복귀)"
								>초기화</button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="text-xs text-gray-600 mt-2">빈 칸 = 기본값 사용, -1 = 무제한, 0 = 사용 불가</p>
	{/if}
</div>
