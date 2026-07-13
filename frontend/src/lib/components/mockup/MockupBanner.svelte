<script lang="ts">
	import { goto } from '$app/navigation';
	import { MOCKUP_COOKIE } from '$lib/mockup/contracts';
	import { tutorialLauncherOpen } from '$lib/tutorial/launcher';

	import Button from '$lib/components/ui/Button.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';

	let {
		label = 'MOCKUP',
		message = '실제 API 호출 없이 가상 데이터로 렌더링 중입니다.',
		tutorial = false,
	}: { label?: string; message?: string; tutorial?: boolean } = $props();

	async function exitMockup() {
		const secure = location.protocol === 'https:' ? '; Secure' : '';
		document.cookie = `${MOCKUP_COOKIE}=; path=/; SameSite=Strict${secure}; max-age=0`;
		await goto('/?mockup=off', { replaceState: true, invalidateAll: true });
	}
</script>

<div class="mockup-banner" role="status" aria-live="polite">
	<div class="mockup-copy">
		<Pill tone="warning" dot>{label || 'MOCKUP'}</Pill>
		<span class="mockup-message">{message}</span>
	</div>
	<div class="mockup-actions">
		{#if tutorial}
			<Button variant="primary" size="xs" onclick={() => tutorialLauncherOpen.set(true)}>튜토리얼 메뉴</Button>
		{/if}
		<Button variant="outline" size="xs" onclick={exitMockup}>종료</Button>
	</div>
</div>

<style>
	.mockup-banner {
		position: fixed;
		left: 50%;
		bottom: 1rem;
		z-index: 70;
		display: flex;
		width: min(calc(100vw - 2rem), 44rem);
		transform: translateX(-50%);
		align-items: center;
		justify-content: space-between;
		gap: 0.875rem;
		border: 1px solid var(--warm-ring);
		border-radius: 999px;
		background: color-mix(in oklab, var(--color-surface-raised) 94%, var(--color-warm));
		box-shadow: var(--glow-warm);
		padding: 0.625rem 0.75rem 0.625rem 0.875rem;
		color: var(--color-ink-0);
	}

	.mockup-copy {
		display: flex;
		min-width: 0;
		align-items: center;
		gap: 0.625rem;
	}

	.mockup-actions {
		display: flex;
		flex-shrink: 0;
		align-items: center;
		gap: 0.5rem;
	}

	.mockup-message {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.8125rem;
		color: var(--color-ink-1);
	}

	@media (max-width: 640px) {
		.mockup-banner {
			align-items: stretch;
			border-radius: 1.25rem;
			flex-direction: column;
		}
		.mockup-message {
			white-space: normal;
		}
	}
</style>
