<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import ChatExtensionsManager from '$lib/components/chat/ChatExtensionsManager.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';

	let { section = 'providers' }: { section?: 'providers' | 'models' | 'tools' } = $props();

	interface Provider {
		id: number;
		name: string;
		provider_type: string;
		api_base: string | null;
		has_api_key: boolean;
		models_dev_provider_id: string | null;
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
		{ value: 'perplexity', label: 'Perplexity (Sonar)' },
		{ value: 'xai', label: 'xAI (Grok)' }
	];
	interface Model {
		id: number;
		provider_id: number;
		model_name: string;
		display_name: string | null;
		is_active: boolean;
		is_title_model?: boolean;
		input_price_per_million: string | null;
		output_price_per_million: string | null;
		effective_input_price_per_million: string | null;
		effective_output_price_per_million: string | null;
		effective_price_source: 'manual' | 'models.dev' | 'litellm' | 'partial' | 'unpriced' | null;
		models_dev_model_id: string | null;
		price_source: 'manual' | 'models.dev' | null;
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
	let mInputPrice = $state('');
	let mOutputPrice = $state('');
	let addingModel = $state(false);

	let editingPrice = $state<Model | null>(null);
	let editInputPrice = $state('');
	let editOutputPrice = $state('');

	interface ModelsDevProvider { id: string; name: string; model_count: number }
	interface ModelsDevModel {
		id: string; name: string; last_updated: string | null;
		input_price_per_million: string | null; output_price_per_million: string | null;
		price_available: boolean; unsupported_price_fields: string[];
	}
	let modelsDevOpen = $state(false);
	let modelsDevProvider = $state<Provider | null>(null);
	let modelsDevProviders = $state<ModelsDevProvider[]>([]);
	let selectedModelsDevProviderId = $state('');
	let modelsDevModels = $state<ModelsDevModel[]>([]);
	let modelsDevSelections = $state<Record<number, string>>({});
	let modelsDevLoading = $state(false);
	let modelsDevError = $state('');
	let modelsDevImporting = $state(false);

	// 등록된 모델 일괄 선택/삭제
	let selectedModelIds = $state<Record<number, boolean>>({});
	let deletingBulk = $state(false);
	const selectedCount = $derived(Object.values(selectedModelIds).filter(Boolean).length);
	const allModelsSelected = $derived(models.length > 0 && selectedCount === models.length);

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
			if (mProviderId === '' && ps.length === 1) mProviderId = ps[0].id;
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
		const prices = pricePayload(mInputPrice, mOutputPrice);
		if (prices === undefined) return;
		addingModel = true;
		try {
			await api.post(
				'/api/v1/chat/admin/models',
				{ provider_id: mProviderId, model_name: mName.trim(), display_name: mDisplay.trim() || null, ...prices },
				token,
				projectId
			);
			mName = '';
			mDisplay = '';
			mInputPrice = '';
			mOutputPrice = '';
			await load();
			toast.success('모델이 추가되었습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '추가 실패');
		} finally {
			addingModel = false;
		}
	}

	function formatPricePerMillion(price: string | null): string {
		if (price === null) return '가격 미확인';
		return price.replace(/(\.\d*?[1-9])0+$/, '$1').replace(/\.0+$/, '');
	}

	function pricePayload(input: string, output: string): { input_price_per_million: string | null; output_price_per_million: string | null } | undefined {
		const normalizedInput = input.trim() || null;
		const normalizedOutput = output.trim() || null;
		if ((normalizedInput === null) !== (normalizedOutput === null)) {
			toast.error('입력·출력 가격은 함께 입력하거나 함께 비워야 합니다');
			return undefined;
		}
		return { input_price_per_million: normalizedInput, output_price_per_million: normalizedOutput };
	}

	function openPriceEditor(model: Model) {
		editingPrice = model;
		editInputPrice = model.input_price_per_million ?? '';
		editOutputPrice = model.output_price_per_million ?? '';
	}

	async function savePrice() {
		if (!editingPrice) return;
		const prices = pricePayload(editInputPrice, editOutputPrice);
		if (!prices) return;
		try {
			await api.patch(`/api/v1/chat/admin/models/${editingPrice.id}`, prices, token, projectId);
			editingPrice = null;
			await load();
			toast.success('모델 가격을 저장했습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '가격 저장 실패');
		}
	}

	async function openModelsDev(provider: Provider) {
		modelsDevOpen = true;
		modelsDevProvider = provider;
		modelsDevError = '';
		modelsDevModels = [];
		modelsDevSelections = {};
		modelsDevLoading = true;
		try {
			const result = await api.get<{ providers: ModelsDevProvider[] }>('/api/v1/chat/admin/models/pricing/models-dev/providers', token, projectId);
			modelsDevProviders = result.providers;
			selectedModelsDevProviderId = provider.models_dev_provider_id || result.providers[0]?.id || '';
			await loadModelsDevProvider();
		} catch (e) {
			modelsDevError = e instanceof ApiError ? e.message : 'models.dev 가격표를 불러오지 못했습니다';
		} finally {
			modelsDevLoading = false;
		}
	}

	async function loadModelsDevProvider() {
		if (!selectedModelsDevProviderId) return;
		modelsDevLoading = true;
		try {
			const result = await api.get<{ models: ModelsDevModel[] }>(
				`/api/v1/chat/admin/models/pricing/models-dev/providers/${encodeURIComponent(selectedModelsDevProviderId)}`,
				token,
				projectId
			);
			modelsDevModels = result.models;
			modelsDevSelections = Object.fromEntries(
				models
					.filter((model) => model.provider_id === modelsDevProvider?.id && model.price_source !== 'manual')
					.flatMap((model) => {
						const exact = result.models.find((external) => external.price_available && external.id === model.model_name);
						return exact ? [[model.id, exact.id]] : [];
					})
			);
		} catch (e) {
			modelsDevError = e instanceof ApiError ? e.message : 'models.dev 모델 목록을 불러오지 못했습니다';
		} finally {
			modelsDevLoading = false;
		}
	}

	async function importModelsDevPrices() {
		if (!modelsDevProvider) return;
		const selections = Object.entries(modelsDevSelections)
			.filter(([, externalId]) => externalId)
			.map(([localModelId, modelsDevModelId]) => ({ local_model_id: Number(localModelId), models_dev_model_id: modelsDevModelId }));
		if (selections.length === 0) {
			toast.error('가격을 적용할 모델을 선택하세요');
			return;
		}
		modelsDevImporting = true;
		try {
			await api.post('/api/v1/chat/admin/models/pricing/models-dev/import', {
				local_provider_id: modelsDevProvider.id,
				models_dev_provider_id: selectedModelsDevProviderId,
				selections
			}, token, projectId);
			modelsDevOpen = false;
			await load();
			toast.success('models.dev 추천 가격을 적용했습니다');
		} catch (e) {
			modelsDevError = e instanceof ApiError ? e.message : '가격 import 실패';
		} finally {
			modelsDevImporting = false;
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

	function toggleAllModels(checked: boolean) {
		const next: Record<number, boolean> = {};
		if (checked) for (const m of models) next[m.id] = true;
		selectedModelIds = next;
	}

	async function deleteSelectedModels() {
		const ids = Object.keys(selectedModelIds)
			.filter((k) => selectedModelIds[Number(k)])
			.map(Number);
		if (ids.length === 0) return;
		if (!(await confirmDialog(`선택한 ${ids.length}개 모델을 삭제하시겠습니까?`))) return;
		deletingBulk = true;
		let ok = 0;
		const failed: string[] = [];
		try {
			for (const id of ids) {
				try {
					await api.delete(`/api/v1/chat/admin/models/${id}`, token, projectId);
					ok++;
				} catch {
					failed.push(String(id));
				}
			}
			selectedModelIds = {};
			await load();
			if (ok > 0) toast.success(`${ok}개 모델을 삭제했습니다`);
			if (failed.length > 0) toast.error(`${failed.length}개 삭제 실패`);
		} finally {
			deletingBulk = false;
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

	// 제목 요약 모델 지정/해제 — 최대 1개만 지정(백엔드가 단일 보장). 요약 호출은 시스템 부담.
	async function setTitleModel(m: Model) {
		try {
			const target = m.is_title_model ? null : m.id;
			await api.put('/api/v1/chat/admin/title-model', { model_id: target }, token, projectId);
			models = models.map((x) => ({ ...x, is_title_model: x.id === target }));
			toast.success(target ? '제목 요약 모델로 지정했습니다' : '제목 요약 모델을 해제했습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '제목 요약 모델 설정 실패');
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

<div class="max-w-4xl p-4 md:p-8">
	<PageHeader
		breadcrumb={section === 'models' ? 'AI 채팅 / 모델 설정' : section === 'tools' ? 'AI 채팅 / 도구 설정' : 'AI 채팅 / 설정'}
		title={section === 'models' ? '모델 설정' : section === 'tools' ? '도구 설정' : '채팅 설정'}
		subtitle={section === 'models'
			? '프로바이더 모델, 가격, 제목 요약 모델을 관리합니다.'
			: section === 'tools'
				? 'MCP 서버, 스킬, 커스텀 HTTP 도구를 관리합니다.'
				: 'LLM 프로바이더와 연결 정보를 관리합니다. API 키는 암호화되어 저장됩니다.'}
	/>

	{#if error}
		<div
			class="mb-4 rounded-lg border border-[var(--color-state-danger)]/40 bg-[var(--color-state-danger)]/10 px-4 py-3 text-sm text-[var(--color-state-danger)]"
		>
			{error}
		</div>
	{/if}

	{#if section === 'providers'}
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
								<button class={rowActionCls} onclick={() => updateKey(p)}>키 변경</button>
								<button class={rowActionCls} onclick={() => toggleProvider(p)}>{p.is_active ? '비활성화' : '활성화'}</button>
								<button class="text-[var(--color-state-danger)] transition-opacity hover:opacity-80" onclick={() => deleteProvider(p.id)}>삭제</button>
							</div>
						</div>

					</div>
				{/each}
			</div>
		{/if}
	</section>
	{/if}

	{#if section === 'models'}
	<!-- 모델 -->
	<section>
		<h3 class="mb-1 text-sm font-semibold text-[var(--color-ink-1)]">모델</h3>
		<p class="mb-3 text-xs text-[var(--color-ink-3)]">
			'제목요약 지정'한 모델은 새 대화 제목을 자동 생성합니다. 이 호출 비용은 사용자 크레딧이 아닌 시스템에서 부담합니다.
		</p>
		<div class="{cardCls} mb-4 p-5">
			<div class="flex flex-col gap-3 sm:flex-row sm:items-center">
				<select class={inputCls} bind:value={mProviderId}>
					<option value="">프로바이더 선택</option>
					{#each providers as p (p.id)}
						<option value={p.id}>{p.name}</option>
					{/each}
				</select>
				<div class="flex shrink-0 gap-2">
					<Button
						variant="secondary"
						onclick={() => {
							if (!mProviderId) return toast.error('프로바이더를 선택하세요');
							void discover(mProviderId);
						}}
						disabled={!mProviderId}
					>
						모델 불러오기
					</Button>
					<Button
						variant="secondary"
						onclick={() => {
							const provider = providers.find((p) => p.id === mProviderId);
							if (provider) void openModelsDev(provider);
						}}
						disabled={!mProviderId}
					>
						models.dev 가격
					</Button>
				</div>
			</div>
			{#if discoverId === mProviderId}
				<div class="mt-4 border-t border-[var(--color-line)] pt-4">
					{#if discovering}
						<p class="text-sm text-[var(--color-ink-3)]">모델 목록을 불러오는 중…</p>
					{:else if available.length === 0}
						<p class="text-sm text-[var(--color-ink-3)]">불러온 모델이 없습니다. API 키/Base URL을 확인하거나 직접 추가하세요.</p>
					{:else}
						<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
							<span class="text-xs text-[var(--color-ink-3)]">
								{availSource === 'api' ? '프로바이더 API' : 'LiteLLM 정적 목록'} · 전체 {available.length}개 · 미등록 {filteredAvailable.length}개
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
		<div class="{cardCls} mb-4 p-5">
			<div class="grid grid-cols-1 gap-3 md:grid-cols-5">
				<select class={inputCls} bind:value={mProviderId}>
					<option value="">프로바이더 선택</option>
					{#each providers as p (p.id)}
						<option value={p.id}>{p.name}</option>
					{/each}
				</select>
				<input class={inputCls} placeholder="모델명 (예: gpt-4o)" bind:value={mName} />
				<input class={inputCls} placeholder="표시 이름 (선택)" bind:value={mDisplay} />
				<input class={inputCls} inputmode="decimal" placeholder="입력 가격 (USD / 1M tokens)" bind:value={mInputPrice} />
				<input class={inputCls} inputmode="decimal" placeholder="출력 가격 (USD / 1M tokens)" bind:value={mOutputPrice} />
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
			<div class="mb-2 flex items-center justify-between gap-3 px-1">
				<label class="flex cursor-pointer items-center gap-2 text-xs text-[var(--color-ink-2)]">
					<input
						type="checkbox"
						checked={allModelsSelected}
						onchange={(e) => toggleAllModels(e.currentTarget.checked)}
					/>
					전체 선택{selectedCount > 0 ? ` (${selectedCount})` : ''}
				</label>
				{#if selectedCount > 0}
					<Button variant="danger-outline" size="sm" onclick={deleteSelectedModels} disabled={deletingBulk}>
						{deletingBulk ? '삭제 중…' : `선택 삭제 (${selectedCount})`}
					</Button>
				{/if}
			</div>
			<div class="space-y-2">
				{#each models as m (m.id)}
					<div class="{cardCls} flex items-center justify-between gap-3 px-4 py-3">
						<div class="flex min-w-0 items-center gap-3">
							<input type="checkbox" bind:checked={selectedModelIds[m.id]} aria-label="{m.display_name || m.model_name} 선택" />
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
								{#if m.is_title_model}
									<span class="rounded bg-[var(--color-accent)]/15 px-1.5 py-0.5 text-xs text-[var(--color-accent)]">
										제목 요약
									</span>
								{/if}
								<Pill tone={m.price_source === 'manual' ? 'success' : m.price_source === 'models.dev' ? 'accent' : 'neutral'} size="xs">
									{m.price_source === 'manual' ? '수동' : m.price_source === 'models.dev' ? 'models.dev' : 'LiteLLM 기본값'}
								</Pill>
							</div>
							<div class="mt-0.5 truncate text-xs text-[var(--color-ink-3)]">{m.model_name} · {providerName(m.provider_id)}</div>
							<div class="mt-1 text-xs text-[var(--color-ink-2)]">
								입력 {formatPricePerMillion(m.effective_input_price_per_million)} · 출력 {formatPricePerMillion(m.effective_output_price_per_million)} USD / 1M tokens
							</div>
						</div>
						</div>
						<div class="flex shrink-0 items-center gap-3 text-xs">
							<button class={rowActionCls} onclick={() => setTitleModel(m)}>
								{m.is_title_model ? '제목요약 해제' : '제목요약 지정'}
							</button>
							<button class={rowActionCls} onclick={() => openPriceEditor(m)}>가격 수정</button>
							<button class={rowActionCls} onclick={() => toggleModel(m)}>{m.is_active ? '비활성화' : '활성화'}</button>
							<button class="text-[var(--color-state-danger)] transition-opacity hover:opacity-80" onclick={() => deleteModel(m.id)}>삭제</button>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>
	{/if}

	{#if section === 'models'}
	<Modal open={editingPrice !== null} onClose={() => (editingPrice = null)}>
		<div class="w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-[var(--color-line)] bg-[var(--color-surface-raised)] p-5 shadow-xl">
			<h3 class="text-base font-semibold text-[var(--color-ink-1)]">모델 가격 수정</h3>
			<p class="mt-1 text-sm text-[var(--color-ink-3)]">두 가격을 함께 저장하거나 모두 비우면 LiteLLM 기본 가격을 사용합니다.</p>
			<div class="mt-4 grid gap-3 sm:grid-cols-2">
				<input class={inputCls} inputmode="decimal" placeholder="입력 USD / 1M tokens" bind:value={editInputPrice} />
				<input class={inputCls} inputmode="decimal" placeholder="출력 USD / 1M tokens" bind:value={editOutputPrice} />
			</div>
			<div class="mt-5 flex justify-end gap-2">
				<Button variant="secondary" onclick={() => (editingPrice = null)}>취소</Button>
				<Button onclick={savePrice}>저장</Button>
			</div>
		</div>
	</Modal>

	<Modal bind:open={modelsDevOpen}>
		<div class="max-h-[calc(100vh-2rem)] w-[min(48rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-[var(--color-line)] bg-[var(--color-surface-raised)] p-5 shadow-xl">
			<h3 class="text-base font-semibold text-[var(--color-ink-1)]">models.dev 추천 가격</h3>
			<p class="mt-1 text-sm text-[var(--color-ink-3)]">
				<a class="underline" href="https://models.dev" target="_blank" rel="noreferrer">models.dev</a>의 기본 input/output 단가만 적용합니다. 수동 확정 가격은 덮어쓰지 않습니다.
			</p>
			{#if modelsDevError}<Alert tone="warning" class="mt-3">{modelsDevError}</Alert>{/if}
			<div class="mt-4">
				<label class="mb-1 block text-sm text-[var(--color-ink-2)]" for="models-dev-provider">가격표 프로바이더</label>
				<select id="models-dev-provider" class={inputCls} bind:value={selectedModelsDevProviderId} onchange={loadModelsDevProvider}>
					{#each modelsDevProviders as provider (provider.id)}<option value={provider.id}>{provider.name} ({provider.model_count})</option>{/each}
				</select>
			</div>
			{#if modelsDevLoading}
				<p class="mt-4 text-sm text-[var(--color-ink-3)]">가격표를 불러오는 중…</p>
			{:else}
				<div class="mt-4 space-y-2">
					{#each models.filter((model) => model.provider_id === modelsDevProvider?.id) as model (model.id)}
						<div class="rounded-lg border border-[var(--color-line)] p-3">
							<div class="flex items-center gap-2">
								<input
									type="checkbox"
									checked={Boolean(modelsDevSelections[model.id])}
									disabled={model.price_source === 'manual'}
									onchange={(event) => {
										modelsDevSelections = {
											...modelsDevSelections,
											[model.id]: event.currentTarget.checked
												? (modelsDevModels.find((external) => external.price_available && external.id === model.model_name)?.id ?? '')
												: ''
										};
									}}
								/>
								<span class="min-w-0 flex-1 truncate text-sm text-[var(--color-ink-1)]">
									{model.model_name}{model.price_source === 'manual' ? ' · 수동 가격 보존' : ''}
								</span>
								<select class={inputCls} disabled={model.price_source === 'manual'} bind:value={modelsDevSelections[model.id]}>
									<option value="">가격표 모델 선택</option>
									{#each modelsDevModels.filter((external) => external.price_available) as external (external.id)}
										<option value={external.id}>{external.id} · ${formatPricePerMillion(external.input_price_per_million)}/${formatPricePerMillion(external.output_price_per_million)} / 1M</option>
									{/each}
								</select>
							</div>
							{#if modelsDevSelections[model.id]}
								{@const selected = modelsDevModels.find((external) => external.id === modelsDevSelections[model.id])}
								{#if selected && selected.unsupported_price_fields.length > 0}
									<Alert tone="warning" class="mt-2">tier/cache/reasoning/audio 단가는 적용하지 않습니다: {selected.unsupported_price_fields.join(', ')}</Alert>
								{/if}
							{/if}
						</div>
					{/each}
				</div>
			{/if}
			<div class="mt-5 flex justify-end gap-2">
				<Button variant="secondary" onclick={() => (modelsDevOpen = false)}>취소</Button>
				<Button onclick={importModelsDevPrices} disabled={modelsDevImporting || modelsDevLoading}>
					{modelsDevImporting ? '적용 중…' : '선택 가격 적용'}
				</Button>
			</div>
		</div>
	</Modal>
	{/if}


	{#if section === 'tools'}
		<div class="mt-2">
			<ChatExtensionsManager base="/api/v1/chat/admin" />
		</div>
	{/if}
</div>
