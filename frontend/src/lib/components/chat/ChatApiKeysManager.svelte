<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import Button from '$lib/components/ui/Button.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import type { ApiKey } from '$lib/api/chatUsage';

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let keys = $state<ApiKey[]>([]);
	let loading = $state(true);
	let name = $state('');
	let creating = $state(false);
	// 발급 직후 평문 키(1회만). 모달로 표시 후 목록 새로고침.
	let issued = $state<{ key: string; key_prefix: string } | null>(null);

	interface CompatDiscovery {
		endpoints: {
			openai: { sdk_base_url: string };
			anthropic: { sdk_base_url: string };
		};
	}
	let sdkBases = $state<{ openai: string; anthropic: string } | null>(null);
	let guideLoading = $state(false);
	let guideError = $state('');
	let guideGeneration = 0;

	function sdkBaseUrl(value: unknown): string {
		if (typeof value !== 'string' || !value.trim()) throw new Error('Missing SDK URL');
		const url = new URL(value);
		if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
			throw new Error('Invalid SDK URL');
		}
		return value;
	}

	async function loadConnectionGuide(requestToken = token, requestProjectId = projectId) {
		const generation = ++guideGeneration;
		sdkBases = null;
		guideError = '';
		guideLoading = Boolean(requestToken);
		if (!requestToken) return;
		try {
			const discovery = await api.get<CompatDiscovery>('/api/v1/chat/compat', requestToken, requestProjectId);
			if (generation !== guideGeneration) return;
			sdkBases = {
				openai: sdkBaseUrl(discovery.endpoints?.openai?.sdk_base_url),
				anthropic: sdkBaseUrl(discovery.endpoints?.anthropic?.sdk_base_url)
			};
		} catch {
			if (generation !== guideGeneration) return;
			guideError = 'Lumen 연결 정보를 불러오지 못했습니다. 서비스 연결 및 공개 API 주소 설정을 확인해 주세요.';
		} finally {
			if (generation === guideGeneration) guideLoading = false;
		}
	}

	const openaiExample = $derived(sdkBases ? `import os

from openai import OpenAI

with OpenAI(
    base_url=${JSON.stringify(sdkBases.openai)},
    api_key=os.environ["LUMEN_API_KEY"],
) as client:
    response = client.chat.completions.create(
        model=os.environ["LUMEN_MODEL"],
        messages=[
            {"role": "user", "content": "Write a short poem about the ocean."}
        ],
    )
    print(response.choices[0].message.content)` : '');

	const anthropicExample = $derived(sdkBases ? `import os

from anthropic import Anthropic

with Anthropic(
    base_url=${JSON.stringify(sdkBases.anthropic)},
    api_key=os.environ["LUMEN_API_KEY"],
) as client:
    response = client.messages.create(
        model=os.environ["LUMEN_MODEL"],
        max_tokens=1024,
        messages=[
            {"role": "user", "content": "Write a short poem about the ocean."}
        ],
    )
    for block in response.content:
        if block.type == "text":
            print(block.text)` : '');

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

	async function copyText(value: string, successMessage = '복사되었습니다') {
		try {
			await navigator.clipboard.writeText(value);
			toast.success(successMessage);
		} catch {
			toast.error('복사 실패 — 수동으로 선택해 복사하세요');
		}
	}

	async function copyKey() {
		if (issued) await copyText(issued.key);
	}

	$effect(() => {
		if (token) void load();
	});

	$effect(() => {
		void loadConnectionGuide(token, projectId);
		return () => { guideGeneration += 1; };
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
	<div class="{cardCls} mt-5 min-w-0 p-5">
		<h4 class="mb-2 text-xs font-semibold text-[var(--color-ink-1)]">연결 방법</h4>
		{#if guideLoading}
			<p class="text-xs text-ink-2" role="status">Lumen 연결 정보를 불러오는 중입니다.</p>
		{:else if guideError}
			<Alert>{guideError}</Alert>
			<Button variant="secondary" size="sm" class="mt-3" onclick={() => loadConnectionGuide()}>
				연결 정보 다시 불러오기
			</Button>
		{:else if sdkBases}
			<p class="mb-2 text-xs text-ink-2">
				Lumen이 제공한 공개 API 주소입니다. 대시보드 주소와 다를 수 있으며, SDK별 base_url을 그대로 사용하세요.
			</p>
			<p class="mb-2 text-xs text-ink-2">
				<code>LUMEN_API_KEY</code> 환경 변수에 발급한 키를,
				<code>LUMEN_MODEL</code>에 모델 선택창의 <strong>ID 복사</strong>로 복사한 API ID를 설정하세요.
				아래 예제는 실제 요청을 보내며 API 사용량이 차감됩니다.
			</p>
			<p class="mb-3 text-xs text-ink-2">패키지 설치: <code>python -m pip install openai anthropic</code></p>
			<div class="mb-1 flex items-center justify-between gap-2">
				<p class="text-xs text-ink-2">OpenAI SDK (Python)</p>
				<Button variant="ghost" size="sm" onclick={() => copyText(openaiExample, 'OpenAI 예제를 복사했습니다')}>
					예제 복사
				</Button>
			</div>
			<pre class="{codeCls} max-w-full whitespace-pre" role="region" aria-label="OpenAI SDK Python 예제"><code>{openaiExample}</code></pre>
			<div class="mb-1 mt-3 flex items-center justify-between gap-2">
				<p class="text-xs text-ink-2">Anthropic SDK (Python)</p>
				<Button variant="ghost" size="sm" onclick={() => copyText(anthropicExample, 'Anthropic 예제를 복사했습니다')}>
					예제 복사
				</Button>
			</div>
			<pre class="{codeCls} max-w-full whitespace-pre" role="region" aria-label="Anthropic SDK Python 예제"><code>{anthropicExample}</code></pre>
		{:else}
			<p class="text-xs text-ink-2">로그인 후 Lumen 연결 정보를 확인할 수 있습니다.</p>
		{/if}
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
