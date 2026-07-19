<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import StatTile from '$lib/components/ui/StatTile.svelte';
	import TableShell from '$lib/components/ui/TableShell.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';

	interface SourceStat {
		source: string;
		tokens: number;
		raw_cost: number;
		request_count: number;
	}
	interface Overview {
		prompt_tokens: number;
		completion_tokens: number;
		total_tokens: number;
		credited_cost: number;
		raw_cost: number;
		request_count: number;
		active_users: number;
		conversation_count: number;
		by_source: SourceStat[];
	}
	interface ModelStat {
		model_name: string;
		prompt_tokens: number;
		completion_tokens: number;
		total_tokens: number;
		credited_cost: number;
		raw_cost: number;
		request_count: number;
	}
	interface UserStat {
		user_id: string;
		project_id: string;
		prompt_tokens: number;
		completion_tokens: number;
		total_tokens: number;
		credited_cost: number;
		raw_cost: number;
		request_count: number;
	}
	interface MonthStat {
		month: string;
		ts: number;
		prompt_tokens: number;
		completion_tokens: number;
		total_tokens: number;
		credited_cost: number;
		raw_cost: number;
		request_count: number;
	}
	interface StatsResponse {
		range: string;
		project_id: string | null;
		overview: Overview;
		by_model: ModelStat[];
		monthly: MonthStat[];
		by_user: UserStat[];
		projects: string[];
	}

	const RANGES = [
		{ value: '30d', label: '30일' },
		{ value: '90d', label: '90일' },
		{ value: '1y', label: '1년' },
		{ value: 'all', label: '전체' }
	];

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const USER_PAGE = 20;

	let range = $state('30d');
	let projectFilter = $state('');
	let data = $state<StatsResponse | null>(null);
	let loading = $state(false);
	let error = $state('');
	// 사용자별 표는 페이지네이션(더보기)으로 누적 — 초기 top-N 이후 /admin/stats/users 로 이어붙임
	let userRows = $state<UserStat[]>([]);
	let userOffset = $state(0);
	let hasMoreUsers = $state(false);
	let loadingMore = $state(false);

	const fmtInt = (n: number) => (n ?? 0).toLocaleString('en-US');
	const fmtCredit = (n: number) => (n ?? 0).toLocaleString('en-US', { maximumFractionDigits: 2 });
	const fmtUsd = (n: number) => `$${(n ?? 0).toFixed(4)}`;

	async function load() {
		if (!token) return;
		loading = true;
		error = '';
		try {
			const qs = new URLSearchParams({ range, user_limit: String(USER_PAGE) });
			if (projectFilter) qs.set('project_id', projectFilter);
			const res = await api.get<StatsResponse>(`/api/v1/chat/admin/stats?${qs.toString()}`, token, projectId);
			data = res;
			userRows = res.by_user ?? [];
			userOffset = userRows.length;
			hasMoreUsers = userRows.length >= USER_PAGE;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '통계 조회 실패';
			data = null;
			userRows = [];
			hasMoreUsers = false;
		} finally {
			loading = false;
		}
	}

	async function loadMoreUsers() {
		if (!token || loadingMore) return;
		loadingMore = true;
		try {
			const qs = new URLSearchParams({ range, limit: String(USER_PAGE), offset: String(userOffset) });
			if (projectFilter) qs.set('project_id', projectFilter);
			const res = await api.get<{ users: UserStat[] }>(
				`/api/v1/chat/admin/stats/users?${qs.toString()}`,
				token,
				projectId
			);
			const more = res.users ?? [];
			userRows = [...userRows, ...more];
			userOffset += more.length;
			hasMoreUsers = more.length >= USER_PAGE;
		} catch {
			hasMoreUsers = false;
		} finally {
			loadingMore = false;
		}
	}

	$effect(() => {
		// range/projectFilter 변경 시 재조회
		void range;
		void projectFilter;
		if (token) void load();
	});

	const overview = $derived(data?.overview);
	const monthly = $derived(data?.monthly ?? []);
	const models = $derived(data?.by_model ?? []);
	const users = $derived(userRows);
	const maxMonthTokens = $derived(Math.max(1, ...monthly.map((m) => m.total_tokens)));
	const maxModelTokens = $derived(Math.max(1, ...models.map((m) => m.total_tokens)));
	const hasData = $derived((overview?.request_count ?? 0) > 0);

	const cardCls = 'rounded-xl border border-[var(--color-line)] bg-[var(--color-surface-raised)]';
	const selectCls =
		'rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-base)] px-3 py-1.5 text-sm text-[var(--color-ink-1)] focus:outline-none focus:border-[var(--color-accent)]';
</script>

<div class="max-w-6xl p-4 md:p-8">
	<PageHeader
		breadcrumb="AI 채팅 / 통계"
		title="채팅 사용량 통계"
		subtitle="전체 시스템의 토큰·크레딧·원가를 사용자별·모델별·월별로 집계합니다."
	/>

	<!-- 필터 -->
	<div class="mb-6 flex flex-wrap items-center gap-3">
		<div class="flex gap-1 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)] p-1">
			{#each RANGES as r (r.value)}
				<button
					onclick={() => (range = r.value)}
					class="rounded px-3 py-1 text-xs font-medium transition-colors {range === r.value
						? 'bg-[var(--color-accent)] text-[var(--color-ink-0)]'
						: 'text-[var(--color-ink-3)] hover:text-[var(--color-ink-1)]'}"
				>
					{r.label}
				</button>
			{/each}
		</div>
		<select class={selectCls} bind:value={projectFilter}>
			<option value="">전체 프로젝트</option>
			{#each data?.projects ?? [] as p (p)}
				<option value={p}>{p}</option>
			{/each}
		</select>
		{#if loading}<span class="text-xs text-[var(--color-ink-3)]">불러오는 중…</span>{/if}
	</div>

	{#if error}
		<div
			class="mb-6 rounded-lg border border-[var(--color-state-danger)] bg-[var(--color-state-danger)]/10 px-4 py-3 text-sm text-[var(--color-state-danger)]"
		>
			{error}
		</div>
	{/if}

	{#if !loading && !hasData}
		<EmptyState headline="사용량 데이터가 없습니다" description="선택한 기간·프로젝트에 기록된 채팅 사용량이 없습니다." />
	{:else if overview}
		<!-- KPI 카드 -->
		<div class="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
			<StatTile label="입력 토큰" value={fmtInt(overview.prompt_tokens)} accent="blue" />
			<StatTile label="출력 토큰" value={fmtInt(overview.completion_tokens)} accent="violet" />
			<StatTile label="총 요청" value={fmtInt(overview.request_count)} accent="cyan" />
			<StatTile label="활성 사용자" value={fmtInt(overview.active_users)} accent="emerald" />
			<StatTile label="차감 크레딧" value={fmtCredit(overview.credited_cost)} accent="amber" />
			<StatTile label="원가 (USD)" value={fmtUsd(overview.raw_cost)} accent="rose" />
		</div>

		<!-- 월별 토큰 추이 -->
		<section class="{cardCls} mb-8 p-5">
			<h3 class="mb-4 text-sm font-semibold text-[var(--color-ink-1)]">월별 토큰 추이</h3>
			{#if monthly.length === 0}
				<p class="text-sm text-[var(--color-ink-3)]">표시할 월별 데이터가 없습니다.</p>
			{:else}
				<div class="flex h-48 items-end gap-3">
					{#each monthly as m (m.month)}
						<div class="flex min-w-0 flex-1 flex-col items-center gap-2">
							<div
								class="flex w-full flex-col-reverse overflow-hidden rounded-t"
								style="height: {(m.total_tokens / maxMonthTokens) * 100}%"
								title="{m.month} · 입력 {fmtInt(m.prompt_tokens)} · 출력 {fmtInt(m.completion_tokens)} · 원가 {fmtUsd(m.raw_cost)}"
							>
								<div
									class="w-full bg-[var(--color-accent)]"
									style="height: {m.total_tokens > 0 ? (m.prompt_tokens / m.total_tokens) * 100 : 0}%"
								></div>
								<div
									class="w-full bg-[var(--color-accent-2)]"
									style="height: {m.total_tokens > 0 ? (m.completion_tokens / m.total_tokens) * 100 : 0}%"
								></div>
							</div>
							<span class="truncate text-xs text-[var(--color-ink-3)]">{m.month}</span>
						</div>
					{/each}
				</div>
				<div class="mt-3 flex items-center gap-4 text-xs text-[var(--color-ink-3)]">
					<span class="flex items-center gap-1.5">
						<span class="inline-block h-2 w-2 rounded-full bg-[var(--color-accent)]"></span>입력 토큰
					</span>
					<span class="flex items-center gap-1.5">
						<span class="inline-block h-2 w-2 rounded-full bg-[var(--color-accent-2)]"></span>출력 토큰
					</span>
				</div>
			{/if}
		</section>

		<!-- 모델별 -->
		<section class="mb-8">
			<h3 class="mb-3 text-sm font-semibold text-[var(--color-ink-1)]">모델별 사용량</h3>
			{#if models.length === 0}
				<p class="text-sm text-[var(--color-ink-3)]">데이터가 없습니다.</p>
			{:else}
				<TableShell>
					<table>
						<thead>
							<tr class="text-xs uppercase tracking-wide">
								<th>모델</th>
								<th class="text-right">비중</th>
								<th class="text-right">입력</th>
								<th class="text-right">출력</th>
								<th class="text-right">총 토큰</th>
								<th class="text-right">요청</th>
								<th class="text-right">크레딧</th>
								<th class="text-right">원가</th>
							</tr>
						</thead>
						<tbody>
							{#each models as m (m.model_name)}
								<tr>
									<td class="text-sm font-medium text-[var(--color-ink-1)]">{m.model_name}</td>
									<td class="w-32">
										<div class="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-surface-sunken)]">
											<div
												class="h-full rounded-full bg-[var(--color-accent)]"
												style="width: {(m.total_tokens / maxModelTokens) * 100}%"
											></div>
										</div>
									</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtInt(m.prompt_tokens)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtInt(m.completion_tokens)}</td>
									<td class="text-right text-sm font-medium text-[var(--color-ink-1)]">{fmtInt(m.total_tokens)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtInt(m.request_count)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtCredit(m.credited_cost)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtUsd(m.raw_cost)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</TableShell>
			{/if}
		</section>

		<!-- 사용자별 -->
		<section>
			<h3 class="mb-3 text-sm font-semibold text-[var(--color-ink-1)]">
				사용자별 사용량 <span class="text-xs font-normal text-[var(--color-ink-3)]">(시스템 부담 제외)</span>
			</h3>
			{#if users.length === 0}
				<p class="text-sm text-[var(--color-ink-3)]">데이터가 없습니다.</p>
			{:else}
				<TableShell>
					<table>
						<thead>
							<tr class="text-xs uppercase tracking-wide">
								<th>사용자</th>
								<th>프로젝트</th>
								<th class="text-right">입력</th>
								<th class="text-right">출력</th>
								<th class="text-right">총 토큰</th>
								<th class="text-right">요청</th>
								<th class="text-right">크레딧</th>
								<th class="text-right">원가</th>
							</tr>
						</thead>
						<tbody>
							{#each users as u (u.user_id + u.project_id)}
								<tr>
									<td class="text-sm font-medium text-[var(--color-ink-1)]">{u.user_id}</td>
									<td class="text-sm text-[var(--color-ink-3)]">{u.project_id}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtInt(u.prompt_tokens)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtInt(u.completion_tokens)}</td>
									<td class="text-right text-sm font-medium text-[var(--color-ink-1)]">{fmtInt(u.total_tokens)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtInt(u.request_count)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtCredit(u.credited_cost)}</td>
									<td class="text-right text-sm text-[var(--color-ink-2)]">{fmtUsd(u.raw_cost)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</TableShell>
				{#if hasMoreUsers}
					<div class="mt-3 flex justify-center">
						<button
							onclick={loadMoreUsers}
							disabled={loadingMore}
							class="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)] px-4 py-1.5 text-sm text-[var(--color-ink-2)] transition-colors hover:text-[var(--color-ink-0)] disabled:opacity-60"
						>
							{loadingMore ? '불러오는 중…' : '더보기'}
						</button>
					</div>
				{/if}
			{/if}
		</section>
	{/if}
</div>
