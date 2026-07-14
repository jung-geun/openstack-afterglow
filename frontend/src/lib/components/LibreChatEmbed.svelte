<script lang="ts">
	import { siteConfig } from '$lib/config/site';
	import Card from '$lib/components/ui/Card.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	const chatUrl = $derived($siteConfig.runtime.librechat_base);

	const ONBOARDED_KEY = 'librechat_onboarded';
	let onboarded = $state(true);

	$effect(() => {
		onboarded = typeof localStorage !== 'undefined' && localStorage.getItem(ONBOARDED_KEY) === '1';
	});

	function openInNewTab() {
		if (typeof localStorage !== 'undefined') localStorage.setItem(ONBOARDED_KEY, '1');
		onboarded = true;
		window.open(chatUrl, '_blank', 'noopener,noreferrer');
	}
</script>

<Card padding="none" class="w-full h-[calc(100vh-8rem)] flex flex-col">
	{#if !chatUrl}
		<div class="w-full h-full flex flex-col items-center justify-center gap-2 text-center px-6">
			<svg class="w-8 h-8 text-[var(--color-ink-3)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
					d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
			</svg>
			<p class="text-sm text-[var(--color-ink-2)]">채팅 서비스가 구성되지 않았습니다</p>
			<p class="text-xs text-[var(--color-ink-3)]">config.toml [chat] base_url 확인</p>
		</div>
	{:else}
		{#if !onboarded}
			<div class="flex flex-col items-center gap-3 text-center px-6 py-8 border-b border-[var(--color-line)] shrink-0">
				<p class="text-sm text-[var(--color-ink-1)]">
					최초 1회는 로그인을 위해 새 탭에서 열어야 합니다
				</p>
				<p class="text-xs text-[var(--color-ink-3)] max-w-md">
					GitLab 로그인 화면은 보안상 이 페이지 안(iframe)에서 표시할 수 없습니다.
					아래 버튼으로 새 탭에서 한 번 로그인하면, 다음부터는 이 화면에서 바로 이용할 수 있습니다.
				</p>
				<Button onclick={openInNewTab}>새 탭에서 로그인하기 ↗</Button>
			</div>
		{/if}
		<div class="flex items-center justify-end px-3 py-1.5 border-b border-[var(--color-line)] shrink-0">
			<a
				href={chatUrl}
				target="_blank"
				rel="noopener noreferrer"
				onclick={() => { if (typeof localStorage !== 'undefined') localStorage.setItem(ONBOARDED_KEY, '1'); }}
				class="text-xs text-[var(--color-ink-3)] hover:text-[var(--color-ink-1)] transition-colors"
			>
				새 탭에서 열기 ↗
			</a>
		</div>
		<iframe
			src={chatUrl}
			class="w-full flex-1 border-0"
			sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-storage-access-by-user-activation"
			loading="lazy"
			title="AI 채팅"
		></iframe>
	{/if}
</Card>
