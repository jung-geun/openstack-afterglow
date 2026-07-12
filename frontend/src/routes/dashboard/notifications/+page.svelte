<script lang="ts">
	import { onMount } from 'svelte';
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

	onMount(load);
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
						<li class="py-3.5 flex items-start gap-3 {a.is_read ? 'opacity-70' : ''}">
							<span class="mt-1.5 w-2 h-2 rounded-full flex-shrink-0" style="background: {severityDotColor(a.severity)};"></span>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2">
									<span class="text-sm font-medium text-[var(--color-ink-0)]">{a.title}</span>
									{#if !a.is_read}
										<span class="text-[9px] uppercase tracking-wide text-[var(--color-accent)] border border-[var(--color-accent)]/40 rounded px-1 py-0.5">new</span>
									{/if}
								</div>
								<p class="text-xs text-[var(--color-ink-2)] mt-1 whitespace-pre-wrap leading-relaxed">{a.body}</p>
								<p class="text-[10px] text-[var(--color-ink-3)] mt-1.5 tabular-nums">{formatIsoDateTime(a.created_at)}</p>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</Card>
	{/if}
</div>
