<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import AdminLoginBrandingPanel from '$lib/components/admin/AdminLoginBrandingPanel.svelte';
	import AdminResourcePoliciesPanel from '$lib/components/admin/AdminResourcePoliciesPanel.svelte';
	import { Card, PageHeader, PageShell } from '$lib/components/ui';

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);
</script>

<PageShell max="7xl">
	<PageHeader
		breadcrumb="SYSTEM / SETTINGS"
		title="기본 설정"
		subtitle="로그인 브랜딩처럼 전역 UI 기본값을 한 곳에서 관리합니다."
	/>

	<div class="settings-stack">
		<Card padding="lg" surface="subtle">
			<div class="settings-intro">
				<p class="eyebrow">Admin defaults</p>
				<h2>서비스 기본값</h2>
				<p>
					관리자 개요는 운영 상태 확인에 집중하고, 로그인 화면처럼 사이트 전체에 적용되는 설정은 이 페이지에서 정리합니다.
				</p>
			</div>
		</Card>

		<AdminLoginBrandingPanel {token} {projectId} />
		<AdminResourcePoliciesPanel {token} {projectId} />
	</div>
</PageShell>

<style>
	.settings-stack {
		display: grid;
		gap: 1rem;
	}

	.settings-intro {
		display: grid;
		gap: 0.35rem;
		max-width: 42rem;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--admin-tone, var(--color-warm));
	}

	h2 {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: var(--color-ink-0);
	}

	p {
		margin: 0;
		font-size: 0.85rem;
		line-height: 1.6;
		color: var(--color-ink-2);
	}
</style>
