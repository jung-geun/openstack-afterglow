<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import Button from '$lib/components/ui/Button.svelte';
	import type { ApiKey } from '$lib/api/chatUsage';

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let keys = $state<ApiKey[]>([]);
	let loading = $state(true);
	let name = $state('');
	let creating = $state(false);
	// 발급 직후 평문 키(1회만). 모달로 표시 후 목록 새로고침.
	let issued = $state<{ key: string; key_prefix: string } | null>(null);

	// 외부 API base URL — 채팅 API는 전용 서브도메인(api.<host>)에서만 열린다(기본 URL과 충돌 방지).
	// 이미 api. 로 시작하면 그대로, 아니면 호스트 앞에 api. 를 붙여 제안한다.
	const origin = $derived.by(() => {
		if (typeof window === 'undefined') return 'https://api.<host>';
		const { protocol, host } = window.location;
		const apiHost = host.startsWith('api.') ? host : `api.${host}`;
		return `${protocol}//${apiHost}`;
	});

	async function load() {
		if (!token) return;
		loading = true;
		try {
			keys = await api.get<ApiKey[]>('/api/v1/chat/api-keys', token, projectId);
		} catch {
			toast.error('API 키 목록을 불러오지 못했습니다');
		} finally {
			loading = false;
		}
	}

	async function create() {
		creating = true;
		try {
			const res = await api.post<{ key: string; key_prefix: string }>(
				'/api/v1/chat/api-keys',
				{ name: name.trim() },
				token,
				projectId
			);
			issued = { key: res.key, key_prefix: res.key_prefix };
			name = '';
			await load();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '발급 실패');
		} finally {
			creating = false;
		}
	}

	async function revoke(id: number) {
		if (!(await confirmDialog('이 API 키를 폐기하시겠습니까? 이 키를 쓰는 연동은 즉시 중단됩니다.'))) return;
		try {
			await api.delete(`/api/v1/chat/api-keys/${id}`, token, projectId);
			await load();
		} catch {
			toast.error('폐기 실패');
		}
	}

	async function copyKey() {
		if (!issued) return;
		try {
			await navigator.clipboard.writeText(issued.key);
			toast.success('복사되었습니다');
		} catch {
			toast.error('복사 실패 — 수동으로 선택해 복사하세요');
		}
	}

	$effect(() => {
		if (token) void load();
	});

	const inputCls =
		'w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-base)] px-3 py-2 text-sm text-[var(--color-ink-1)] focus:outline-none focus:border-[var(--color-accent)]';
	const cardCls = 'rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)]';
	const codeCls = 'block overflow-x-auto rounded-lg bg-[var(--color-surface-sunken)] p-3 font-mono text-xs text-[var(--color-ink-2)]';
</script>

<section>
	<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">API 키</h3>
	<p class="mb-3 text-xs text-[var(--color-ink-3)]">
		외부 프로그램(OpenAI/Anthropic SDK)에서 이 채팅에 접속할 때 쓰는 키입니다. 사용량은 내 지갑·월 쿼터에서
		차감되며, 웹과 분리된 API 통계로 집계됩니다.
	</p>

	<div class="{cardCls} mb-4 p-5">
		<div class="flex flex-col gap-3 sm:flex-row">
			<input class={inputCls} placeholder="키 이름 (예: 내 노트북 CLI)" bind:value={name} />
			<Button onclick={create} disabled={creating}>{creating ? '발급 중…' : '+ 새 API 키 발급'}</Button>
		</div>
	</div>

	{#if loading}
		<div class="{cardCls} h-16 animate-pulse"></div>
	{:else if keys.length === 0}
		<p class="px-1 text-sm text-[var(--color-ink-3)]">발급된 API 키가 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each keys as k (k.id)}
				<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{k.name || '(이름 없음)'}</span>
							{#if !k.is_active}<span class="rounded bg-[var(--color-line)] px-1.5 py-0.5 text-xs text-[var(--color-ink-3)]">폐기됨</span>{/if}
						</div>
						<div class="mt-0.5 font-mono text-xs text-[var(--color-ink-3)]">
							{k.key_prefix}…{#if k.last_used_at} · 마지막 사용 {new Date(k.last_used_at).toLocaleString()}{:else} · 미사용{/if}
						</div>
					</div>
					{#if k.is_active}
						<button class="shrink-0 text-xs text-[var(--color-state-danger)] hover:opacity-80" onclick={() => revoke(k.id)}>폐기</button>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	<!-- SDK 사용 예시 -->
	<div class="{cardCls} mt-5 p-5">
		<h4 class="mb-2 text-xs font-semibold text-[var(--color-ink-1)]">연결 방법</h4>
		<p class="mb-2 text-xs text-[var(--color-ink-3)]">
			채팅 API는 전용 서브도메인(<span class="font-mono">{origin.replace(/^https?:\/\//, '')}</span>)에서만 열립니다. OpenAI/Anthropic SDK의 base_url을 아래처럼 설정하세요.
		</p>
		<p class="mb-1 text-xs text-[var(--color-ink-3)]">OpenAI SDK (Python)</p>
		<code class={codeCls}>from openai import OpenAI
client = OpenAI(base_url="{origin}/v1", api_key="sk-afgl-...")
client.chat.completions.create(model="...", messages=[...])</code>
		<p class="mb-1 mt-3 text-xs text-[var(--color-ink-3)]">Anthropic SDK (Python)</p>
		<code class={codeCls}>from anthropic import Anthropic
client = Anthropic(base_url="{origin}", api_key="sk-afgl-...")
client.messages.create(model="...", max_tokens=1024, messages=[...])</code>
	</div>
</section>

<!-- 발급 직후 평문 키 1회 표시 모달 -->
{#if issued}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
		<div class="{cardCls} w-full max-w-lg p-6">
			<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">API 키가 발급되었습니다</h3>
			<p class="mb-3 text-xs text-[var(--color-state-danger)]">
				이 키는 지금 한 번만 표시됩니다. 안전한 곳에 저장하세요. 창을 닫으면 다시 볼 수 없습니다.
			</p>
			<code class={codeCls}>{issued.key}</code>
			<div class="mt-4 flex justify-end gap-2">
				<Button variant="ghost" onclick={copyKey}>복사</Button>
				<Button onclick={() => (issued = null)}>완료</Button>
			</div>
		</div>
	</div>
{/if}
