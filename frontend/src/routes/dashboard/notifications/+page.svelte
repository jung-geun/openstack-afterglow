<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import { formatIsoDateTime } from '$lib/utils/format';
	import type { AnnouncementUser, AnnouncementSeverity } from '$lib/types/announcements';
	import type { DashboardAlert, DashboardOverviewQuotas } from '$lib/types/quotas';

	let announcements = $state<AnnouncementUser[]>([]);
	let quotaAlerts = $state<DashboardAlert[]>([]);
	let loading = $state(true);
	let error = $state('');
	let expandedId = $state<number | null>(null);
	let initialized = false;
	let reloadedForFocus: string | null = null;

	function toggleExpanded(id: number) {
		expandedId = expandedId === id ? null : id;
	}

	// 대시보드 카드/종 드롭다운에서 특정 공지로 딥링크(?focus=<id>) 진입 시 자동 펼침 + 스크롤.
	// $derived 문자열은 동일 id 재탐색 시 동등성 때문에 $effect를 깨우지 못하므로,
	// 최초 마운트와 같은 라우트 내 재탐색 모두에서 호출되는 afterNavigate로 처리한다.
	async function applyFocus() {
		const raw = $page.url.searchParams.get('focus');
		if (!raw) return;
		const id = Number(raw);
		if (!Number.isInteger(id)) return;
		if (!announcements.some((a) => a.id === id)) {
			// 페이지가 열린 뒤 발행된 공지로 딥링크된 경우 목록이 스테일할 수 있다 — 1회만 재조회
			if (reloadedForFocus === raw) return;
			reloadedForFocus = raw;
			await load();
			if (!announcements.some((a) => a.id === id)) return;
		}
		expandedId = id;
		requestAnimationFrame(() => {
			document.getElementById(`announcement-${id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
		});
	}

	afterNavigate(() => {
		void (async () => {
			if (!initialized) {
				initialized = true;
				await load();
			}
			await applyFocus();
		})();
	});

	function severityDotColor(severity: AnnouncementSeverity | DashboardAlert['severity']): string {
		if (severity === 'danger') return 'var(--color-state-danger)';
		if (severity === 'warning') return 'var(--color-state-warning)';
		return 'var(--color-accent)';
	}

	async function load() {
		loading = true;
		error = '';
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			const [items, quotas] = await Promise.all([
				api.get<AnnouncementUser[]>('/api/v1/announcements', token, projectId),
				api
					.get<DashboardOverviewQuotas>('/api/v1/dashboard/quotas?view=overview', token, projectId)
					.catch(() => null),
			]);
			announcements = items;
			quotaAlerts = quotas?.alerts ?? [];

			// 알림함 진입 시 미읽음 공지를 읽음 처리 (best-effort — 실패해도 목록 표시는 진행)
			const unread = items.filter((a) => !a.is_read);
			if (unread.length > 0) {
				await Promise.allSettled(
					unread.map((a) => api.post(`/api/v1/announcements/${a.id}/read`, {}, token, projectId)),
				);
				announcements = announcements.map((a) => ({ ...a, is_read: true }));
			}
		} catch (e) {
			error = e instanceof ApiError ? e.message : '알림을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

</script>

<div class="p-4 md:p-8 max-w-3xl mx-auto">
	<div class="flex items-center gap-3 mb-4">
		<a
			href="/dashboard"
			class="inline-flex items-center gap-1.5 text-xs text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)] transition-colors px-2.5 py-1.5 rounded-md hover:bg-[var(--color-surface-sunken)]"
		>
			<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
			대시보드로 돌아가기
		</a>
	</div>

	<PageHeader breadcrumb="" title="알림함" subtitle="쿼터 경고와 관리자 공지를 확인합니다" />

	{#if error}
		<Alert tone="danger" class="mb-4">{error}</Alert>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		{#if quotaAlerts.length > 0}
			<Card padding="lg" class="mb-4">
				<p class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] mb-3">현재 쿼터 경고</p>
				<ul class="flex flex-col gap-2">
					{#each quotaAlerts as alert}
						<li class="flex items-start gap-2.5 text-sm">
							<span class="mt-1.5 w-2 h-2 rounded-full flex-shrink-0" style="background: {severityDotColor(alert.severity)};"></span>
							<span class="flex-1 text-[var(--color-ink-0)] text-xs leading-snug">{alert.message}</span>
							{#if alert.count > 1}
								<span class="text-[10px] text-[var(--color-ink-3)] tabular-nums flex-shrink-0">×{alert.count}</span>
							{/if}
						</li>
					{/each}
				</ul>
			</Card>
		{/if}

		<Card padding="lg">
			<p class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] mb-3">공지 히스토리</p>
			{#if announcements.length === 0}
				<p class="text-sm text-[var(--color-ink-3)] py-4">받은 공지가 없습니다</p>
			{:else}
				<ul class="flex flex-col divide-y divide-[var(--color-line)]">
					{#each announcements as a (a.id)}
						<li id="announcement-{a.id}">
							<button
								onclick={() => toggleExpanded(a.id)}
								aria-expanded={expandedId === a.id}
								class="w-full text-left py-3.5 flex items-start gap-3 group {a.is_read && expandedId !== a.id ? 'opacity-70' : ''}"
							>
								<span class="mt-1.5 w-2 h-2 rounded-full flex-shrink-0" style="background: {severityDotColor(a.severity)};"></span>
								<span class="flex-1 min-w-0">
									<span class="flex items-center gap-2">
										<span class="text-sm font-medium text-[var(--color-ink-0)] group-hover:text-[var(--color-accent)] transition-colors">{a.title}</span>
										{#if !a.is_read}
											<span class="text-[9px] uppercase tracking-wide text-[var(--color-accent)] border border-[var(--color-accent)]/40 rounded px-1 py-0.5">new</span>
										{/if}
									</span>
									<span class="block text-[10px] text-[var(--color-ink-3)] mt-1 tabular-nums">{formatIsoDateTime(a.created_at)} · {a.created_by_username}</span>
								</span>
								<svg
									class="w-3.5 h-3.5 mt-1 flex-shrink-0 text-[var(--color-ink-3)] transition-transform {expandedId === a.id ? 'rotate-180' : ''}"
									fill="none" stroke="currentColor" viewBox="0 0 24 24"
								><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
							</button>
							{#if expandedId === a.id}
								<div class="ml-5 mb-3.5 rounded-lg px-4 py-3" style="background: var(--color-surface-sunken);">
									<p class="text-xs text-[var(--color-ink-1)] whitespace-pre-wrap leading-relaxed">{a.body}</p>
									<dl class="mt-3 pt-3 border-t border-[var(--color-line)] grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
										<dt class="text-[var(--color-ink-3)]">발송자</dt>
										<dd class="text-[var(--color-ink-1)]">{a.created_by_username}</dd>
										<dt class="text-[var(--color-ink-3)]">발송 시각</dt>
										<dd class="text-[var(--color-ink-1)] tabular-nums">{formatIsoDateTime(a.created_at)}</dd>
										{#if a.starts_at}
											<dt class="text-[var(--color-ink-3)]">게시 시작</dt>
											<dd class="text-[var(--color-ink-1)] tabular-nums">{formatIsoDateTime(a.starts_at)}</dd>
										{/if}
										<dt class="text-[var(--color-ink-3)]">만료 시각</dt>
										<dd class="text-[var(--color-ink-1)] tabular-nums">{a.ends_at ? formatIsoDateTime(a.ends_at) : '만료 없음'}</dd>
									</dl>
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</Card>
	{/if}
</div>
