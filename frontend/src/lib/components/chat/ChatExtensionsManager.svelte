<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import Button from '$lib/components/ui/Button.svelte';

	// base: '/api/v1/chat/admin' (관리자 global) 또는 '/api/v1/chat' (사용자 본인)
	// only: 특정 섹션만 렌더('mcp' | 'tools' | 'skills'). 미지정 시 전부.
	let { base, only }: { base: string; only?: 'mcp' | 'tools' | 'skills' } = $props();

	interface AuthRequirement {
		key: string;
		label: string;
		description?: string;
	}
	interface McpServer {
		id: number;
		scope: string;
		name: string;
		transport: string;
		url: string | null;
		headers?: Record<string, string> | null; // 값은 서버에서 마스킹됨
		has_headers?: boolean;
		auth_requirements?: AuthRequirement[];
		auth_mode?: 'none' | 'headers' | 'oauth';
		is_active: boolean;
	}
	interface McpOAuthStatus {
		required: boolean;
		connected: boolean;
		expires_at: string | null;
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
	interface Skill {
		id: number;
		scope: string;
		name: string;
		description: string | null;
		instructions: string;
		is_active: boolean;
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let mcps = $state<McpServer[]>([]);
	let tools = $state<CustomTool[]>([]);
	let skills = $state<Skill[]>([]);
	let loading = $state(true);

	const isAdmin = $derived(base.includes('/admin'));

	let mName = $state('');
	let mTransport = $state('http');
	let mUrl = $state('');
	let mHeaders = $state(''); // 'Header-Name: value' 줄 단위 입력 → dict 파싱
	let mAuthReq = $state(''); // 'Authorization: Notion Token' 줄 단위 → 사용자 인증 요구사항
	let addingMcp = $state(false);

	// 사용자별 인증 값 입력 상태(사용자 뷰): 서버 id별 펼침 + 입력 값 + 충족 여부.
	let credOpenId = $state<number | null>(null);
	let credValues = $state<Record<string, string>>({});
	let credFilled = $state<string[]>([]);
	let savingCred = $state(false);
	let oauthStatus = $state<Record<number, McpOAuthStatus>>({});
	let connectingOAuthId = $state<number | null>(null);

	/** 'Header-Name: value' 형식 줄들을 dict 로 파싱. 빈 줄/':' 없는 줄 무시. */
	function parseHeaders(text: string): Record<string, string> {
		const out: Record<string, string> = {};
		for (const line of text.split('\n')) {
			const idx = line.indexOf(':');
			if (idx <= 0) continue;
			const k = line.slice(0, idx).trim();
			const v = line.slice(idx + 1).trim();
			if (k && v) out[k] = v;
		}
		return out;
	}

	/** 'Authorization: Notion Token' 줄들을 [{key,label}] 요구사항으로 파싱. */
	function parseRequirements(text: string): AuthRequirement[] {
		const out: AuthRequirement[] = [];
		for (const line of text.split('\n')) {
			const idx = line.indexOf(':');
			const key = (idx > 0 ? line.slice(0, idx) : line).trim();
			if (!key) continue;
			const label = idx > 0 ? line.slice(idx + 1).trim() || key : key;
			out.push({ key, label });
		}
		return out;
	}

	async function openCred(m: McpServer) {
		if (credOpenId === m.id) {
			credOpenId = null;
			return;
		}
		credOpenId = m.id;
		credValues = {};
		credFilled = [];
		for (const r of m.auth_requirements ?? []) credValues[r.key] = '';
		try {
			const st = await api.get<{ filled_keys: string[] }>(
				`${base}/mcp-servers/${m.id}/credentials`,
				token,
				projectId
			);
			credFilled = st.filled_keys ?? [];
			// 이미 채운 값은 마스킹 표시(재전송 시 유지).
			for (const k of credFilled) credValues[k] = '••••••';
		} catch {
			/* 상태 조회 실패는 무시 — 빈 폼으로 입력 */
		}
	}

	async function saveCred(m: McpServer) {
		savingCred = true;
		try {
			const st = await api.put<{ filled_keys: string[] }>(
				`${base}/mcp-servers/${m.id}/credentials`,
				{ values: credValues },
				token,
				projectId
			);
			credFilled = st.filled_keys ?? [];
			toast.success('인증 정보가 저장되었습니다');
			credOpenId = null;
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장 실패');
		} finally {
			savingCred = false;
		}
	}


	async function connectOAuth(m: McpServer) {
		connectingOAuthId = m.id;
		try {
			const result = await api.post<{ authorization_url: string }>(
				`${base}/mcp-servers/${m.id}/oauth/start`,
				{},
				token,
				projectId
			);
			if (!result.authorization_url) throw new Error('missing authorization URL');
			window.location.assign(result.authorization_url);
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : 'OAuth 연결을 시작하지 못했습니다');
		} finally {
			connectingOAuthId = null;
		}
	}

	async function disconnectOAuth(m: McpServer) {
		if (!(await confirmDialog(`${m.name} OAuth 연결을 해제하시겠습니까?`))) return;
		try {
			await api.delete(`${base}/mcp-servers/${m.id}/oauth`, token, projectId);
			await load();
			toast.success('OAuth 연결을 해제했습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : 'OAuth 연결 해제 실패');
		}
	}
	let tName = $state('');
	let tDesc = $state('');
	let tMethod = $state('GET');
	let tUrl = $state('');
	let addingTool = $state(false);

	let sName = $state('');
	let sDesc = $state('');
	let sInstructions = $state('');
	let addingSkill = $state(false);

	async function load() {
		if (!token) return;
		loading = true;
		try {
			const [ms, ts, ss] = await Promise.all([
				api.get<McpServer[]>(`${base}/mcp-servers`, token, projectId),
				api.get<CustomTool[]>(`${base}/custom-tools`, token, projectId),
				api.get<Skill[]>(`${base}/skills`, token, projectId)
			]);
			mcps = ms;
			tools = ts;
			skills = ss;
			oauthStatus = Object.fromEntries(
				await Promise.all(
					ms
						.filter((mcp) => mcp.auth_mode === 'oauth')
						.map(async (mcp) => [
							mcp.id,
							await api.get<McpOAuthStatus>(`${base}/mcp-servers/${mcp.id}/oauth`, token, projectId)
						] as const)
				)
			);
		} catch {
			toast.error('목록을 불러오지 못했습니다');
		} finally {
			loading = false;
		}
	}

	async function addSkill() {
		if (!sName.trim() || !sInstructions.trim()) {
			toast.error('이름과 지침을 입력하세요');
			return;
		}
		addingSkill = true;
		try {
			await api.post(
				`${base}/skills`,
				{ name: sName.trim(), description: sDesc.trim() || null, instructions: sInstructions.trim() },
				token,
				projectId
			);
			sName = '';
			sDesc = '';
			sInstructions = '';
			await load();
			toast.success('스킬이 추가되었습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '추가 실패');
		} finally {
			addingSkill = false;
		}
	}

	async function addMcp() {
		if (!mName.trim()) {
			toast.error('이름을 입력하세요');
			return;
		}
		if (!mUrl.trim()) {
			toast.error('원격 MCP 서버는 URL이 필요합니다');
			return;
		}
		addingMcp = true;
		try {
			const headers = parseHeaders(mHeaders);
			const requirements = parseRequirements(mAuthReq);
			await api.post(
				`${base}/mcp-servers`,
				{
					name: mName.trim(),
					transport: mTransport,
					url: mUrl.trim(),
					...(Object.keys(headers).length ? { headers } : {}),
					...(requirements.length ? { auth_requirements: requirements } : {})
				},
				token,
				projectId
			);
			mName = '';
			mUrl = '';
			mHeaders = '';
			mAuthReq = '';
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

	async function removeItem(kind: 'mcp-servers' | 'custom-tools' | 'skills', id: number) {
		if (!(await confirmDialog('삭제하시겠습니까?'))) return;
		try {
			await api.delete(`${base}/${kind}/${id}`, token, projectId);
			await load();
		} catch {
			toast.error('삭제 실패');
		}
	}

	async function toggle(kind: 'mcp-servers' | 'custom-tools' | 'skills', id: number, isActive: boolean) {
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
{#if !only || only === 'mcp'}
<section class="mb-8">
	<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">원격 MCP 서버</h3>
	<p class="mb-3 text-xs text-[var(--color-ink-3)]">원격(http streamable / sse) MCP 서버를 연결해 도구를 사용합니다. 스코프: {base.includes('/admin') ? '전체 공용' : '내 전용'}</p>
	<div class="{cardCls} mb-4 p-5">
		<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
			<input class={inputCls} placeholder="이름" bind:value={mName} />
			<select class={inputCls} bind:value={mTransport}>
				<option value="http">http (streamable)</option>
				<option value="sse">sse</option>
			</select>
			<input class={inputCls} placeholder="URL (예: https://mcp.example/mcp)" bind:value={mUrl} />
		</div>
		<div class="mt-3">
			<label class="mb-1 block text-xs text-[var(--color-ink-3)]" for="mcp-headers">
				인증 헤더 (선택) — 한 줄에 하나, <code>이름: 값</code> 형식. 값은 암호화 저장됩니다.
			</label>
			<textarea
				id="mcp-headers"
				class="{inputCls} font-mono"
				rows="2"
				placeholder={'Authorization: Bearer <token>\nX-Api-Key: <key>'}
				bind:value={mHeaders}
			></textarea>
		</div>
		<div class="mt-3">
			<label class="mb-1 block text-xs text-[var(--color-ink-3)]" for="mcp-authreq">
				사용자 인증 요구사항 (선택) — 한 줄에 하나, <code>헤더키: 라벨</code>. Notion MCP URL은 자동으로 사용자별 OAuth 연결을 요구합니다. 다른 정적 헤더 인증만 여기에서 선언하세요.
			</label>
			<textarea
				id="mcp-authreq"
				class="{inputCls} font-mono"
				rows="2"
				placeholder={'Authorization: Service access token\nX-Api-Key: External service key'}
				bind:value={mAuthReq}
			></textarea>
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
				<div class={cardCls}>
					<div class="flex items-center justify-between gap-3 px-4 py-3">
						<div class="min-w-0">
							<div class="flex items-center gap-2">
								<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{m.name}</span>
								<span class={badge(m.is_active)}>{m.is_active ? '활성' : '비활성'}</span>
								<span class="text-xs text-[var(--color-ink-3)]">{m.transport}</span>
								{#if m.has_headers}<span class="text-xs text-[var(--color-ink-3)]" title="공용 인증 헤더 설정됨">🔒</span>{/if}
								{#if m.auth_requirements?.length}<span class="text-xs text-[var(--color-ink-3)]" title="사용자별 인증 필요">👤🔑</span>{/if}
								{#if m.auth_mode === 'oauth'}
									<span class="text-xs text-[var(--color-state-info)]" title="사용자별 OAuth 연결 필요">OAuth</span>
								{/if}
							</div>
							{#if m.url}<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{m.url}</div>{/if}
						</div>
						<div class="flex shrink-0 items-center gap-3 text-xs">
							{#if !isAdmin && m.auth_requirements?.length}
								<button class="text-[var(--color-accent)] hover:opacity-80" onclick={() => openCred(m)}>인증 정보</button>
							{/if}
							{#if !isAdmin && m.auth_mode === 'oauth'}
								{#if oauthStatus[m.id]?.connected}
									<button class="text-[var(--color-state-success)] hover:opacity-80" onclick={() => disconnectOAuth(m)}>OAuth 연결됨</button>
								{:else}
									<button class="text-[var(--color-accent)] hover:opacity-80" disabled={connectingOAuthId === m.id} onclick={() => connectOAuth(m)}>
										{connectingOAuthId === m.id ? '연결 준비 중…' : `${m.name} OAuth 연결`}
									</button>
								{/if}
							{/if}
							<button class="text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)]" onclick={() => toggle('mcp-servers', m.id, m.is_active)}>{m.is_active ? '비활성화' : '활성화'}</button>
							<button class="text-[var(--color-state-danger)] hover:opacity-80" onclick={() => removeItem('mcp-servers', m.id)}>삭제</button>
						</div>
					</div>
					{#if credOpenId === m.id && m.auth_requirements?.length}
						<div class="border-t border-[var(--color-line)] px-4 py-3">
							<p class="mb-2 text-xs text-[var(--color-ink-3)]">이 서버에 사용할 <b>내 인증 정보</b>를 입력하세요. 값은 암호화 저장되며 나에게만 적용됩니다.</p>
							<div class="space-y-2">
								{#each m.auth_requirements as r (r.key)}
									<div>
										<label class="mb-0.5 block text-xs text-[var(--color-ink-2)]" for="cred-{m.id}-{r.key}">
											{r.label}
											{#if credFilled.includes(r.key)}<span class="ml-1 text-[var(--color-state-success)]">✓ 저장됨</span>{/if}
											<span class="text-[var(--color-ink-3)]">({r.key})</span>
										</label>
										<input
											id="cred-{m.id}-{r.key}"
											class={inputCls}
											type="password"
											placeholder={credFilled.includes(r.key) ? '저장됨 — 변경하려면 새 값 입력' : '값 입력'}
											bind:value={credValues[r.key]}
										/>
									</div>
								{/each}
							</div>
							<div class="mt-3 flex justify-end gap-2">
								<Button variant="ghost" onclick={() => (credOpenId = null)}>닫기</Button>
								<Button onclick={() => saveCred(m)} disabled={savingCred}>{savingCred ? '저장 중…' : '저장'}</Button>
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</section>
{/if}

<!-- 커스텀 HTTP 툴 -->
{#if !only || only === 'tools'}
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

<!-- 스킬 (선택 시 채팅 지침으로 주입) -->
{#if !only || only === 'skills'}
<section class="mt-8">
	<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">스킬</h3>
	<p class="mb-3 text-xs text-[var(--color-ink-3)]">채팅에서 선택하면 지침(SKILL.md)이 대화에 주입됩니다(모든 모델). 스코프: {base.includes('/admin') ? '전체 공용' : '내 전용'}</p>
	<div class="{cardCls} mb-4 p-5">
		<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
			<input class={inputCls} placeholder="스킬 이름" bind:value={sName} />
			<input class={inputCls} placeholder="설명 (선택)" bind:value={sDesc} />
		</div>
		<div class="mt-3">
			<label class="mb-1 block text-xs text-[var(--color-ink-3)]" for="skill-instructions">
				지침 (instructions) — 선택 시 system 프리앰블에 주입됩니다. 암호화 저장.
			</label>
			<textarea
				id="skill-instructions"
				class={inputCls}
				rows="5"
				placeholder="예: 당신은 코드 리뷰 전문가입니다. 항상 보안·성능·가독성 순으로 검토하고…"
				bind:value={sInstructions}
			></textarea>
		</div>
		<div class="mt-3 flex justify-end">
			<Button onclick={addSkill} disabled={addingSkill}>{addingSkill ? '추가 중…' : '+ 스킬 추가'}</Button>
		</div>
	</div>
	{#if loading}
		<div class="{cardCls} h-16 animate-pulse"></div>
	{:else if skills.length === 0}
		<p class="px-1 text-sm text-[var(--color-ink-3)]">등록된 스킬이 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each skills as s (s.id)}
				<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
					<div class="min-w-0">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{s.name}</span>
							<span class={badge(s.is_active)}>{s.is_active ? '활성' : '비활성'}</span>
						</div>
						{#if s.description}<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{s.description}</div>{/if}
					</div>
					<div class="flex shrink-0 items-center gap-3 text-xs">
						<button class="text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)]" onclick={() => toggle('skills', s.id, s.is_active)}>{s.is_active ? '비활성화' : '활성화'}</button>
						<button class="text-[var(--color-state-danger)] hover:opacity-80" onclick={() => removeItem('skills', s.id)}>삭제</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>
{/if}
