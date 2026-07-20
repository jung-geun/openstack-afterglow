<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import Button from '$lib/components/ui/Button.svelte';

	// base: '/api/v1/chat/admin' (관리자 global) 또는 '/api/v1/chat' (사용자 본인)
	// only: 특정 섹션만 렌더('mcp' | 'tools'). 미지정 시 둘 다.
	let { base, only }: { base: string; only?: 'mcp' | 'tools' } = $props();

	interface McpServer {
		id: number;
		scope: string;
		name: string;
		transport: string;
		url: string | null;
		is_active: boolean;
	}
	interface CustomTool {
		id: number;
		scope: string;
		name: string;
		description: string;
		method: string;
		url: string;
		is_active: boolean;
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let mcps = $state<McpServer[]>([]);
	let tools = $state<CustomTool[]>([]);
	let loading = $state(true);

	let mName = $state('');
	let mTransport = $state('http');
	let mUrl = $state('');
	let addingMcp = $state(false);

	let tName = $state('');
	let tDesc = $state('');
	let tMethod = $state('GET');
	let tUrl = $state('');
	let addingTool = $state(false);

	async function load() {
		if (!token) return;
		loading = true;
		try {
			const [ms, ts] = await Promise.all([
				api.get<McpServer[]>(`${base}/mcp-servers`, token, projectId),
				api.get<CustomTool[]>(`${base}/custom-tools`, token, projectId)
			]);
			mcps = ms;
			tools = ts;
		} catch {
			toast.error('목록을 불러오지 못했습니다');
		} finally {
			loading = false;
		}
	}

	async function addMcp() {
		if (!mName.trim()) {
			toast.error('이름을 입력하세요');
			return;
		}
		addingMcp = true;
		try {
			await api.post(
				`${base}/mcp-servers`,
				{ name: mName.trim(), transport: mTransport, url: mUrl.trim() || null },
				token,
				projectId
			);
			mName = '';
			mUrl = '';
			await load();
			toast.success('MCP 서버가 추가되었습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '추가 실패');
		} finally {
			addingMcp = false;
		}
	}

	async function addTool() {
		if (!tName.trim() || !tUrl.trim()) {
			toast.error('이름과 URL을 입력하세요');
			return;
		}
		addingTool = true;
		try {
			await api.post(
				`${base}/custom-tools`,
				{ name: tName.trim(), description: tDesc.trim() || tName.trim(), method: tMethod, url: tUrl.trim() },
				token,
				projectId
			);
			tName = '';
			tDesc = '';
			tUrl = '';
			await load();
			toast.success('커스텀 툴이 추가되었습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '추가 실패');
		} finally {
			addingTool = false;
		}
	}

	async function removeItem(kind: 'mcp-servers' | 'custom-tools', id: number) {
		if (!(await confirmDialog('삭제하시겠습니까?'))) return;
		try {
			await api.delete(`${base}/${kind}/${id}`, token, projectId);
			await load();
		} catch {
			toast.error('삭제 실패');
		}
	}

	async function toggle(kind: 'mcp-servers' | 'custom-tools', id: number, isActive: boolean) {
		try {
			await api.patch(`${base}/${kind}/${id}`, { is_active: !isActive }, token, projectId);
			await load();
		} catch {
			toast.error('변경 실패');
		}
	}

	$effect(() => {
		if (token) void load();
	});

	const inputCls =
		'w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-base)] px-3 py-2 text-sm text-[var(--color-ink-1)] focus:outline-none focus:border-[var(--color-accent)]';
	const cardCls = 'rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)]';
	const badge = (active: boolean) =>
		`rounded px-1.5 py-0.5 text-xs ${active ? 'bg-[var(--color-state-success)]/15 text-[var(--color-state-success)]' : 'bg-[var(--color-line)] text-[var(--color-ink-3)]'}`;
</script>

<!-- MCP 서버 -->
{#if only !== 'tools'}
<section class="mb-8">
	<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">MCP 서버</h3>
	<p class="mb-3 text-xs text-[var(--color-ink-3)]">등록·관리 (실행은 추후 지원). 스코프: {base.includes('/admin') ? '전체 공용' : '내 전용'}</p>
	<div class="{cardCls} mb-4 p-5">
		<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
			<input class={inputCls} placeholder="이름" bind:value={mName} />
			<select class={inputCls} bind:value={mTransport}>
				<option value="http">http</option>
				<option value="sse">sse</option>
				<option value="stdio">stdio</option>
			</select>
			<input class={inputCls} placeholder="URL (예: https://mcp.example)" bind:value={mUrl} />
		</div>
		<div class="mt-3 flex justify-end">
			<Button onclick={addMcp} disabled={addingMcp}>{addingMcp ? '추가 중…' : '+ MCP 서버 추가'}</Button>
		</div>
	</div>
	{#if loading}
		<div class="{cardCls} h-16 animate-pulse"></div>
	{:else if mcps.length === 0}
		<p class="px-1 text-sm text-[var(--color-ink-3)]">등록된 MCP 서버가 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each mcps as m (m.id)}
				<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{m.name}</span>
							<span class={badge(m.is_active)}>{m.is_active ? '활성' : '비활성'}</span>
							<span class="text-xs text-[var(--color-ink-3)]">{m.transport}</span>
						</div>
						{#if m.url}<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{m.url}</div>{/if}
					</div>
					<div class="flex shrink-0 items-center gap-3 text-xs">
						<button class="text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)]" onclick={() => toggle('mcp-servers', m.id, m.is_active)}>{m.is_active ? '비활성화' : '활성화'}</button>
						<button class="text-[var(--color-state-danger)] hover:opacity-80" onclick={() => removeItem('mcp-servers', m.id)}>삭제</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>
{/if}

<!-- 커스텀 HTTP 툴 -->
{#if only !== 'mcp'}
<section>
	<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">커스텀 HTTP 툴</h3>
	<p class="mb-3 text-xs text-[var(--color-ink-3)]">LLM 이 호출할 수 있는 외부 HTTP 엔드포인트. 스코프: {base.includes('/admin') ? '전체 공용' : '내 전용'}</p>
	<div class="{cardCls} mb-4 p-5">
		<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
			<input class={inputCls} placeholder="툴 이름 (영숫자/_)" bind:value={tName} />
			<input class={inputCls} placeholder="설명" bind:value={tDesc} />
			<select class={inputCls} bind:value={tMethod}>
				<option value="GET">GET</option>
				<option value="POST">POST</option>
			</select>
			<input class={inputCls} placeholder="URL" bind:value={tUrl} />
		</div>
		<div class="mt-3 flex justify-end">
			<Button onclick={addTool} disabled={addingTool}>{addingTool ? '추가 중…' : '+ 커스텀 툴 추가'}</Button>
		</div>
	</div>
	{#if loading}
		<div class="{cardCls} h-16 animate-pulse"></div>
	{:else if tools.length === 0}
		<p class="px-1 text-sm text-[var(--color-ink-3)]">등록된 커스텀 툴이 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each tools as t (t.id)}
				<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{t.name}</span>
							<span class={badge(t.is_active)}>{t.is_active ? '활성' : '비활성'}</span>
							<span class="text-xs text-[var(--color-ink-3)]">{t.method}</span>
						</div>
						<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{t.description} · {t.url}</div>
					</div>
					<div class="flex shrink-0 items-center gap-3 text-xs">
						<button class="text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)]" onclick={() => toggle('custom-tools', t.id, t.is_active)}>{t.is_active ? '비활성화' : '활성화'}</button>
						<button class="text-[var(--color-state-danger)] hover:opacity-80" onclick={() => removeItem('custom-tools', t.id)}>삭제</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>
{/if}
