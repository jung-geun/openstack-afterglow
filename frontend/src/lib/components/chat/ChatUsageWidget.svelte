<script lang="ts">
	import type { ChatUsage } from '$lib/api/chatTree';
	let { usage }: { usage: ChatUsage } = $props();

	const monthTokens = $derived(
		(usage.month_prompt_tokens ?? 0) + (usage.month_completion_tokens ?? 0)
	);
	const credit = $derived(usage.month_credited_cost ?? 0);
	const quotaMax = $derived(usage.quota_max ?? 0);
	const quotaUsed = $derived(usage.quota_used ?? 0);
	const hasQuota = $derived(quotaMax > 0);
	const quotaPct = $derived(hasQuota ? Math.min(100, Math.round((quotaUsed / quotaMax) * 100)) : 0);
	const quotaTone = $derived(quotaPct >= 90 ? 'danger' : quotaPct >= 70 ? 'warning' : 'ok');

	function fmt(n: number): string {
		return n.toLocaleString('en-US');
	}
	function fmtCredit(n: number): string {
		return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
	}
</script>

<div class="usage" title="이번 달 사용량 (입력+출력 토큰 · 크레딧)">
	<div class="usage-line">
		<span class="usage-label">이번 달</span>
		<span class="usage-val">{fmt(monthTokens)} 토큰</span>
		<span class="usage-sep">·</span>
		<span class="usage-val">크레딧 {fmtCredit(credit)}</span>
	</div>
	{#if hasQuota}
		<div class="bar" aria-label="월 쿼터 사용률 {quotaPct}%">
			<div class="bar-fill" data-tone={quotaTone} style="width: {quotaPct}%"></div>
		</div>
		<div class="quota-txt">{fmt(quotaUsed)} / {fmt(quotaMax)} ({quotaPct}%)</div>
	{/if}
</div>

<style>
	.usage {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.2rem;
		min-width: 0;
	}
	.usage-line {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.72rem;
		color: var(--color-ink-2);
		white-space: nowrap;
	}
	.usage-label {
		color: var(--color-ink-3);
	}
	.usage-val {
		font-variant-numeric: tabular-nums;
	}
	.usage-sep {
		color: var(--color-ink-3);
	}
	.bar {
		width: 8rem;
		height: 0.3rem;
		border-radius: 999px;
		background: var(--color-surface-sunken);
		overflow: hidden;
	}
	.bar-fill {
		height: 100%;
		border-radius: 999px;
		background: var(--color-accent);
		transition: width 0.3s ease;
	}
	.bar-fill[data-tone='warning'] {
		background: var(--color-state-warning);
	}
	.bar-fill[data-tone='danger'] {
		background: var(--color-state-danger);
	}
	.quota-txt {
		font-size: 0.66rem;
		color: var(--color-ink-3);
		font-variant-numeric: tabular-nums;
	}
</style>
