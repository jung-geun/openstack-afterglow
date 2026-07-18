<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	interface Provider {
		id: number;
		name: string;
		api_base: string | null;
		has_api_key: boolean;
		is_active: boolean;
		margin_multiplier: number;
	}
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
	let pApiBase = $state('');
	let pApiKey = $state('');
	let addingProvider = $state(false);

	let mProviderId = $state<number | ''>('');
	let mName = $state('');
	let mDisplay = $state('');
	let addingModel = $state(false);

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
				{ name: pName.trim(), api_base: pApiBase.trim() || null, api_key: pApiKey.trim() || null },
				token,
				projectId
			);
			pName = '';
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
			<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
				<input class={inputCls} placeholder="이름 (예: openai)" bind:value={pName} />
				<input class={inputCls} placeholder="API Base (선택)" bind:value={pApiBase} />
				<input class={inputCls} type="password" placeholder="API 키" bind:value={pApiKey} />
			</div>
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
</div>
