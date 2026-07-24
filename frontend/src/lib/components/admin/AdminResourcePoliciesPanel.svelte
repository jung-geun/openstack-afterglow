<script lang="ts">
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api/client';
	import { Alert, Button, Card, SelectInput } from '$lib/components/ui';

	interface ResourceOption {
		id: string;
		name: string;
		is_external?: boolean;
		is_shared?: boolean;
	}

	interface ResourcePolicy {
		key: string;
		resource_kind: string;
		title: string;
		external_only: boolean;
		resource_id: string | null;
		resource_name: string | null;
	}

	interface Props {
		token?: string;
		projectId?: string;
	}

	let { token, projectId }: Props = $props();
	let policies = $state<ResourcePolicy[]>([]);
	let options = $state<Record<string, ResourceOption[]>>({});
	let selections = $state<Record<string, string>>({});
	let loading = $state(true);
	let loadingCatalog = $state<string | null>(null);
	let saving = $state<string | null>(null);
	let error = $state('');
	let notice = $state('');

	async function loadPolicies() {
		loading = true;
		error = '';
		try {
			policies = await api.get<ResourcePolicy[]>('/api/v1/admin/resource-policies', token, projectId);
			selections = Object.fromEntries(policies.map((policy) => [policy.key, policy.resource_id ?? '']));
		} catch (cause) {
			error = cause instanceof ApiError ? `리소스 정책을 조회하지 못했습니다: ${cause.message}` : '리소스 정책을 조회하지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function loadOptions(policy: ResourcePolicy) {
		if (options[policy.key]) return;
		loadingCatalog = policy.key;
		error = '';
		try {
			const catalog = await api.get<{ options: ResourceOption[] }>(
				`/api/v1/admin/resource-policies/catalog/${encodeURIComponent(policy.key)}`,
				token,
				projectId
			);
			options = { ...options, [policy.key]: catalog.options };
		} catch (cause) {
			error = cause instanceof ApiError ? `OpenStack 목록을 조회하지 못했습니다: ${cause.message}` : 'OpenStack 목록을 조회하지 못했습니다';
		} finally {
			loadingCatalog = null;
		}
	}

	async function save(policy: ResourcePolicy) {
		saving = policy.key;
		error = '';
		notice = '';
		try {
			const updated = await api.put<ResourcePolicy>(
				`/api/v1/admin/resource-policies/${encodeURIComponent(policy.key)}`,
				{ resource_id: selections[policy.key] || null },
				token,
				projectId
			);
			policies = policies.map((item) => (item.key === updated.key ? { ...item, ...updated } : item));
			notice = `${policy.title} 정책을 저장했습니다.`;
		} catch (cause) {
			error = cause instanceof ApiError ? `정책 저장 실패: ${cause.message}` : '정책 저장 실패';
		} finally {
			saving = null;
		}
	}

	onMount(loadPolicies);
</script>

<Card padding="lg" surface="subtle">
	<div class="heading">
		<div>
			<p class="eyebrow">Infrastructure policies</p>
			<h2>OpenStack 리소스 정책</h2>
			<p>프로비저닝 범위에 맞게 검증된 리소스 ID만 저장합니다. 이름은 표시용 스냅샷이며 실행에는 ID를 사용합니다.</p>
		</div>
	</div>

	{#if error}<Alert tone="danger">{error}</Alert>{/if}
	{#if notice}<Alert tone="success">{notice}</Alert>{/if}

	{#if loading}
		<p class="muted">정책을 불러오는 중…</p>
	{:else}
		<div class="policy-list">
			{#each policies as policy (policy.key)}
				<section class="policy-row">
					<div class="policy-copy">
						<strong>{policy.title}</strong>
						<span>{policy.resource_kind}{policy.external_only ? ' · external only' : ''}</span>
					</div>
					{#if options[policy.key]}
						<SelectInput bind:value={selections[policy.key]} ariaLabel={`${policy.title} 선택`}>
							<option value="">선택 안 함</option>
							{#each options[policy.key] as option (option.id)}
								<option value={option.id}>{option.name} ({option.id.slice(0, 8)})</option>
							{/each}
						</SelectInput>
					{:else}
						<span class="selection">{policy.resource_name ? `${policy.resource_name} (${policy.resource_id?.slice(0, 8)})` : '선택 안 함'}</span>
					{/if}
					<div class="actions">
						<Button variant="secondary" size="sm" onclick={() => loadOptions(policy)} disabled={loadingCatalog === policy.key}>
							{loadingCatalog === policy.key ? '조회 중…' : '목록 조회'}
						</Button>
						<Button variant="primary" size="sm" onclick={() => save(policy)} disabled={saving === policy.key}>
							{saving === policy.key ? '저장 중…' : '저장'}
						</Button>
					</div>
				</section>
			{/each}
		</div>
	{/if}
</Card>

<style>
	.heading, .policy-copy, .policy-list { display: grid; gap: 0.5rem; }
	.heading { margin-bottom: 1rem; }
	.eyebrow { margin: 0; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: var(--admin-tone, var(--color-warm)); }
	h2 { margin: 0; font-size: 1rem; color: var(--color-ink-0); }
	p, .muted, .policy-copy span, .selection { margin: 0; color: var(--color-ink-2); font-size: 0.82rem; line-height: 1.5; }
	.policy-row { display: grid; grid-template-columns: minmax(11rem, 1fr) minmax(13rem, 1.2fr) auto; align-items: center; gap: 0.75rem; border-top: 1px solid var(--color-line-2); padding: 0.75rem 0; }
	.policy-copy strong { color: var(--color-ink-0); font-size: 0.86rem; }
	.selection { padding: 0.5rem 0.75rem; }
	.actions { display: flex; gap: 0.4rem; }
	@media (max-width: 720px) { .policy-row { grid-template-columns: 1fr; } .actions { justify-content: flex-end; } }
</style>
