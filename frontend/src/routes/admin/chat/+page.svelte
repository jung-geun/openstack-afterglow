<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import ChatExtensionsManager from '$lib/components/chat/ChatExtensionsManager.svelte';

	interface Provider {
		id: number;
		name: string;
		provider_type: string;
		api_base: string | null;
		has_api_key: boolean;
		is_active: boolean;
		margin_multiplier: number;
	}

	// litellm custom_llm_provider — 내부에서 litellm 이 각 API 형식으로 중계한다.
	// OpenAI 호환 엔드포인트는 'openai' + API Base 로 연결. 그 외는 각 provider 타입 선택.
	const PROVIDER_TYPES: { value: string; label: string }[] = [
		{ value: 'openai', label: 'OpenAI (및 OpenAI 호환 API)' },
		{ value: 'anthropic', label: 'Anthropic (Claude)' },
		{ value: 'gemini', label: 'Google Gemini (AI Studio)' },
		{ value: 'vertex_ai', label: 'Google Vertex AI (GCP)' },
		{ value: 'azure', label: 'Azure OpenAI' },
		{ value: 'bedrock', label: 'AWS Bedrock' },
		{ value: 'ollama', label: 'Ollama (로컬)' },
		{ value: 'mistral', label: 'Mistral' },
		{ value: 'cohere', label: 'Cohere' },
		{ value: 'groq', label: 'Groq' },
		{ value: 'deepseek', label: 'DeepSeek' },
		{ value: 'together_ai', label: 'Together AI' },
		{ value: 'openrouter', label: 'OpenRouter' },
		{ value: 'xai', label: 'xAI (Grok)' }
	];
	interface Model {
		id: number;
		provider_id: number;
		model_name: string;
		display_name: string | null;
		is_active: boolean;
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let providers = $state<Provider[]>([]);
	let models = $state<Model[]>([]);
	let loading = $state(true);
	let error = $state('');

	let pName = $state('');
	let pType = $state('openai');
	let pApiBase = $state('');
	let pApiKey = $state('');
	let addingProvider = $state(false);

	let mProviderId = $state<number | ''>('');
	let mName = $state('');
	let mDisplay = $state('');
	let addingModel = $state(false);

	// 모델 discovery (프로바이더 API에서 목록 불러오기 → 필터 → 선택 등록)
	let discoverId = $state<number | null>(null);
	let available = $state<string[]>([]);
	let availSource = $state('');
	let availFilter = $state('');
	let selectedAvail = $state<Record<string, boolean>>({});
	let discovering = $state(false);
	let registeringBulk = $state(false);

	function registeredNames(providerId: number): Set<string> {
		return new Set(models.filter((m) => m.provider_id === providerId).map((m) => m.model_name));
	}

	const filteredAvailable = $derived.by(() => {
		if (discoverId === null) return [];
		const reg = registeredNames(discoverId);
		const f = availFilter.toLowerCase();
		return available.filter((m) => m.toLowerCase().includes(f) && !reg.has(m));
	});

	async function load() {
		if (!token) return;
		loading = true;
		try {
			const [ps, ms] = await Promise.all([
				api.get<Provider[]>('/api/v1/chat/admin/providers', token, projectId),
				api.get<Model[]>('/api/v1/chat/admin/models', token, projectId)
			]);
			providers = ps;
			models = ms;
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function addProvider() {
		if (!pName.trim()) {
			toast.error('프로바이더 이름을 입력하세요');
			return;
		}
		addingProvider = true;
		try {
			await api.post(
				'/api/v1/chat/admin/providers',
				{
					name: pName.trim(),
					provider_type: pType,
					api_base: pApiBase.trim() || null,
					api_key: pApiKey.trim() || null
				},
				token,
				projectId
			);
			pName = '';
			pType = 'openai';
			pApiBase = '';
			pApiKey = '';
			await load();
			toast.success('프로바이더가 추가되었습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '추가 실패');
		} finally {
			addingProvider = false;
		}
	}

	async function deleteProvider(id: number) {
		if (!(await confirmDialog('프로바이더를 삭제하시겠습니까? 연결된 모델도 함께 삭제됩니다.'))) return;
		try {
			await api.delete(`/api/v1/chat/admin/providers/${id}`, token, projectId);
			await load();
		} catch {
			toast.error('삭제 실패');
		}
	}

	async function toggleProvider(p: Provider) {
		try {
			await api.patch(`/api/v1/chat/admin/providers/${p.id}`, { is_active: !p.is_active }, token, projectId);
			await load();
		} catch {
			toast.error('변경 실패');
		}
	}

	async function updateKey(p: Provider) {
		const key = prompt(`${p.name} 의 새 API 키를 입력하세요 (비우면 제거)`);
		if (key === null) return;
		try {
			await api.patch(`/api/v1/chat/admin/providers/${p.id}`, { api_key: key.trim() || null }, token, projectId);
			await load();
			toast.success('API 키가 갱신되었습니다');
		} catch {
			toast.error('갱신 실패');
		}
	}

	async function addModel() {
		if (!mProviderId || !mName.trim()) {
			toast.error('프로바이더와 모델명을 입력하세요');
			return;
		}
		addingModel = true;
		try {
			await api.post(
				'/api/v1/chat/admin/models',
				{ provider_id: mProviderId, model_name: mName.trim(), display_name: mDisplay.trim() || null },
				token,
				projectId
			);
			mName = '';
			mDisplay = '';
			await load();
			toast.success('모델이 추가되었습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '추가 실패');
		} finally {
			addingModel = false;
		}
	}

	async function discover(providerId: number) {
		if (discoverId === providerId) {
			discoverId = null;
			return;
		}
		discoverId = providerId;
		discovering = true;
		available = [];
		availSource = '';
		availFilter = '';
		selectedAvail = {};
		try {
			const res = await api.get<{ models: string[]; source: string }>(
				`/api/v1/chat/admin/providers/${providerId}/available-models`,
				token,
				projectId
			);
			available = res.models;
			availSource = res.source;
			if (res.models.length === 0) {
				toast.error('모델을 찾지 못했습니다 (API 키/Base URL 확인)');
			}
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '모델 조회 실패');
			discoverId = null;
		} finally {
			discovering = false;
		}
	}

	async function registerSelected() {
		if (discoverId === null) return;
		const names = Object.keys(selectedAvail).filter((k) => selectedAvail[k]);
		if (names.length === 0) {
			toast.error('등록할 모델을 선택하세요');
			return;
		}
		registeringBulk = true;
		let ok = 0;
		const failed: string[] = [];
		try {
			for (const name of names) {
				try {
					await api.post(
						'/api/v1/chat/admin/models',
						{ provider_id: discoverId, model_name: name },
						token,
						projectId
					);
					ok++;
				} catch {
					failed.push(name);
				}
			}
			await load();
			if (ok > 0) toast.success(`${ok}개 모델을 등록했습니다`);
			if (failed.length > 0) toast.error(`${failed.length}개 등록 실패 (중복 등)`);
			selectedAvail = {};
		} finally {
			registeringBulk = false;
		}
	}

	function toggleAllFiltered(checked: boolean) {
		const next = { ...selectedAvail };
		for (const m of filteredAvailable) next[m] = checked;
		selectedAvail = next;
	}

	async function deleteModel(id: number) {
		if (!(await confirmDialog('모델을 삭제하시겠습니까?'))) return;
		try {
			await api.delete(`/api/v1/chat/admin/models/${id}`, token, projectId);
			await load();
		} catch {
			toast.error('삭제 실패');
		}
	}

	async function toggleModel(m: Model) {
		try {
			await api.patch(`/api/v1/chat/admin/models/${m.id}`, { is_active: !m.is_active }, token, projectId);
			await load();
		} catch {
			toast.error('변경 실패');
		}
	}

	function providerName(id: number): string {
		return providers.find((p) => p.id === id)?.name ?? String(id);
	}

	$effect(() => {
		if (token) void load();
	});

	const inputCls =
		'w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-base)] px-3 py-2 text-sm text-[var(--color-ink-1)] focus:outline-none focus:border-[var(--color-accent)]';
	const cardCls = 'rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)]';
	const rowActionCls = 'text-[var(--color-ink-2)] hover:text-[var(--color-ink-0)] transition-colors';
</script>

<div class="p-4 md:p-8 max-w-4xl">
	<PageHeader
		breadcrumb="AI 채팅 / 설정"
		title="채팅 설정"
		subtitle="LLM 프로바이더와 모델을 등록합니다. API 키는 암호화되어 저장됩니다."
	/>

	{#if error}
		<div
			class="mb-4 rounded-lg border border-[var(--color-state-danger)]/40 bg-[var(--color-state-danger)]/10 px-4 py-3 text-sm text-[var(--color-state-danger)]"
		>
			{error}
		</div>
	{/if}

	<!-- 프로바이더 -->
	<section class="mb-8">
		<h3 class="mb-3 text-sm font-semibold text-[var(--color-ink-1)]">LLM 프로바이더</h3>
		<div class="{cardCls} mb-4 p-5">
			<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
				<input class={inputCls} placeholder="이름 (예: openai-prod)" bind:value={pName} />
				<select class={inputCls} bind:value={pType}>
					{#each PROVIDER_TYPES as pt (pt.value)}
						<option value={pt.value}>{pt.label}</option>
					{/each}
				</select>
				<input class={inputCls} placeholder="API Base (OpenAI 호환/커스텀 엔드포인트, 선택)" bind:value={pApiBase} />
				<input class={inputCls} type="password" placeholder="API 키" bind:value={pApiKey} />
			</div>
			<p class="mt-2 text-xs text-[var(--color-ink-3)]">
				타입은 내부 litellm 중계 형식입니다. OpenAI 호환 엔드포인트(vLLM·LM Studio 등)는 'OpenAI 호환' + API Base 로 연결하세요.
			</p>
			<div class="mt-3 flex justify-end">
				<Button onclick={addProvider} disabled={addingProvider}>
					{addingProvider ? '추가 중…' : '+ 프로바이더 추가'}
				</Button>
			</div>
		</div>

		{#if loading}
			<div class="{cardCls} h-20 animate-pulse"></div>
		{:else if providers.length === 0}
			<p class="px-1 text-sm text-[var(--color-ink-3)]">등록된 프로바이더가 없습니다.</p>
		{:else}
			<div class="space-y-2">
				{#each providers as p (p.id)}
					<div class="space-y-0">
						<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
							<div class="min-w-0">
								<div class="flex items-center gap-2">
									<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{p.name}</span>
									<span
										class="rounded px-1.5 py-0.5 text-xs {p.is_active
											? 'bg-[var(--color-state-success)]/15 text-[var(--color-state-success)]'
											: 'bg-[var(--color-line)] text-[var(--color-ink-3)]'}"
									>
										{p.is_active ? '활성' : '비활성'}
									</span>
									<span
										class="rounded px-1.5 py-0.5 text-xs {p.has_api_key
											? 'bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
											: 'bg-[var(--color-state-warning)]/15 text-[var(--color-state-warning)]'}"
									>
										{p.has_api_key ? '키 설정됨' : '키 없음'}
									</span>
									<span class="rounded bg-[var(--color-line)] px-1.5 py-0.5 text-xs text-[var(--color-ink-2)]">{p.provider_type}</span>
								</div>
								{#if p.api_base}
									<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{p.api_base}</div>
								{/if}
							</div>
							<div class="flex shrink-0 items-center gap-3 text-xs">
								<button class={rowActionCls} onclick={() => discover(p.id)}>
									{discoverId === p.id ? '닫기' : '모델 불러오기'}
								</button>
								<button class={rowActionCls} onclick={() => updateKey(p)}>키 변경</button>
								<button class={rowActionCls} onclick={() => toggleProvider(p)}>{p.is_active ? '비활성화' : '활성화'}</button>
								<button class="text-[var(--color-state-danger)] transition-opacity hover:opacity-80" onclick={() => deleteProvider(p.id)}>삭제</button>
							</div>
						</div>

						{#if discoverId === p.id}
							<div class="mt-2 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-sunken)] p-4">
								{#if discovering}
									<p class="text-sm text-[var(--color-ink-3)]">모델 목록을 불러오는 중…</p>
								{:else if available.length === 0}
									<p class="text-sm text-[var(--color-ink-3)]">불러온 모델이 없습니다. API 키/Base URL을 확인하거나 위에서 직접 추가하세요.</p>
								{:else}
									<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
										<span class="text-xs text-[var(--color-ink-3)]">
											{availSource === 'api' ? '프로바이더 API' : 'litellm 정적 목록'} · 전체 {available.length}개 · 미등록 {filteredAvailable.length}개
										</span>
										<div class="flex items-center gap-2 text-xs">
											<button class={rowActionCls} onclick={() => toggleAllFiltered(true)}>전체 선택</button>
											<button class={rowActionCls} onclick={() => toggleAllFiltered(false)}>선택 해제</button>
										</div>
									</div>
									<input class="{inputCls} mb-3" placeholder="모델 필터 (예: gpt-4)" bind:value={availFilter} />
									<div class="max-h-64 space-y-1 overflow-y-auto rounded border border-[var(--color-line)] bg-[var(--color-surface-base)] p-2">
										{#each filteredAvailable as mid (mid)}
											<label class="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-[var(--color-ink-1)] hover:bg-[var(--color-line)]">
												<input type="checkbox" bind:checked={selectedAvail[mid]} />
												<span class="truncate">{mid}</span>
											</label>
										{:else}
											<p class="px-2 py-1 text-sm text-[var(--color-ink-3)]">필터에 맞는 미등록 모델이 없습니다.</p>
										{/each}
									</div>
									<div class="mt-3 flex justify-end">
										<Button onclick={registerSelected} disabled={registeringBulk}>
											{registeringBulk ? '등록 중…' : '선택 모델 등록'}
										</Button>
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<!-- 모델 -->
	<section>
		<h3 class="mb-3 text-sm font-semibold text-[var(--color-ink-1)]">모델</h3>
		<div class="{cardCls} mb-4 p-5">
			<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
				<select class={inputCls} bind:value={mProviderId}>
					<option value="">프로바이더 선택</option>
					{#each providers as p (p.id)}
						<option value={p.id}>{p.name}</option>
					{/each}
				</select>
				<input class={inputCls} placeholder="모델명 (예: gpt-4o)" bind:value={mName} />
				<input class={inputCls} placeholder="표시 이름 (선택)" bind:value={mDisplay} />
			</div>
			<div class="mt-3 flex justify-end">
				<Button onclick={addModel} disabled={addingModel || providers.length === 0}>
					{addingModel ? '추가 중…' : '+ 모델 추가'}
				</Button>
			</div>
		</div>

		{#if loading}
			<div class="{cardCls} h-20 animate-pulse"></div>
		{:else if models.length === 0}
			<p class="px-1 text-sm text-[var(--color-ink-3)]">등록된 모델이 없습니다.</p>
		{:else}
			<div class="space-y-2">
				{#each models as m (m.id)}
					<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
						<div class="min-w-0">
							<div class="flex items-center gap-2">
								<span class="truncate text-sm font-medium text-[var(--color-ink-1)]">{m.display_name || m.model_name}</span>
								<span
									class="rounded px-1.5 py-0.5 text-xs {m.is_active
										? 'bg-[var(--color-state-success)]/15 text-[var(--color-state-success)]'
										: 'bg-[var(--color-line)] text-[var(--color-ink-3)]'}"
								>
									{m.is_active ? '활성' : '비활성'}
								</span>
							</div>
							<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{m.model_name} · {providerName(m.provider_id)}</div>
						</div>
						<div class="flex shrink-0 items-center gap-3 text-xs">
							<button class={rowActionCls} onclick={() => toggleModel(m)}>{m.is_active ? '비활성화' : '활성화'}</button>
							<button class="text-[var(--color-state-danger)] transition-opacity hover:opacity-80" onclick={() => deleteModel(m.id)}>삭제</button>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<!-- MCP 서버 / 커스텀 툴 (전체 공용) -->
	<div class="mt-10 border-t border-[var(--color-line)] pt-8">
		<ChatExtensionsManager base="/api/v1/chat/admin" />
	</div>
</div>
