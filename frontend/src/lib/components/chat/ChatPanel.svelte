<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import Card from '$lib/components/ui/Card.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	interface Conversation {
		id: string;
		title: string | null;
		model_name: string | null;
		updated_at: string | null;
	}
	interface Message {
		role: string;
		content: string;
		streaming?: boolean;
	}
	interface AvailableModel {
		model_name: string;
		display_name: string;
	}
	interface SseEvent {
		type: string;
		text?: string;
		message?: string;
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let conversations = $state<Conversation[]>([]);
	let models = $state<AvailableModel[]>([]);
	let selectedModel = $state('');
	let activeConvId = $state<string | null>(null);
	let messages = $state<Message[]>([]);
	let input = $state('');
	let sending = $state(false);
	let error = $state<string | null>(null);

	let scrollEl = $state<HTMLDivElement | null>(null);

	async function loadConversations() {
		if (!token || !projectId) return;
		try {
			conversations = await api.get<Conversation[]>('/api/v1/chat/conversations', token, projectId);
		} catch (e) {
			error = e instanceof Error ? e.message : '대화 목록을 불러오지 못했습니다';
		}
	}

	async function loadModels() {
		if (!token || !projectId) return;
		try {
			models = await api.get<AvailableModel[]>('/api/v1/chat/models', token, projectId);
			if (!selectedModel && models.length) selectedModel = models[0].model_name;
		} catch {
			models = [];
		}
	}

	async function loadMessages(convId: string) {
		if (!token || !projectId) return;
		try {
			messages = await api.get<Message[]>(
				`/api/v1/chat/conversations/${convId}/messages`,
				token,
				projectId
			);
		} catch (e) {
			error = e instanceof Error ? e.message : '메시지를 불러오지 못했습니다';
		}
	}

	async function selectConversation(conv: Conversation) {
		if (sending) return;
		activeConvId = conv.id;
		if (conv.model_name) selectedModel = conv.model_name;
		error = null;
		await loadMessages(conv.id);
	}

	function newConversation() {
		if (sending) return;
		activeConvId = null;
		messages = [];
		error = null;
	}

	async function ensureConversation(firstMessage: string): Promise<string | null> {
		if (activeConvId) return activeConvId;
		if (!token || !projectId) return null;
		const conv = await api.post<Conversation>(
			'/api/v1/chat/conversations',
			{ title: firstMessage.slice(0, 60), model_name: selectedModel || null },
			token,
			projectId
		);
		activeConvId = conv.id;
		conversations = [conv, ...conversations];
		return conv.id;
	}

	async function send() {
		const text = input.trim();
		if (!text || sending || !token || !projectId) return;
		if (!selectedModel) {
			error = '사용 가능한 모델이 없습니다. 관리자에게 문의하세요.';
			return;
		}
		error = null;
		sending = true;

		let convId: string | null;
		try {
			convId = await ensureConversation(text);
		} catch (e) {
			error = e instanceof Error ? e.message : '대화를 생성하지 못했습니다';
			sending = false;
			return;
		}
		if (!convId) {
			sending = false;
			return;
		}

		input = '';
		messages = [...messages, { role: 'user', content: text }, { role: 'assistant', content: '', streaming: true }];
		const idx = messages.length - 1;

		api.postSse<SseEvent>(
			`/api/v1/chat/conversations/${convId}/completions`,
			{ message: text, model: selectedModel },
			token,
			projectId,
			(evt) => {
				if (evt.type === 'token' && evt.text) {
					messages[idx].content += evt.text;
				} else if (evt.type === 'error') {
					error = evt.message || '모델 응답 중 오류가 발생했습니다';
					messages[idx].streaming = false;
					sending = false;
				} else if (evt.type === 'done') {
					messages[idx].streaming = false;
					sending = false;
					void loadConversations();
				}
			},
			(err) => {
				error = err.message || '스트리밍 중 오류가 발생했습니다';
				messages[idx].streaming = false;
				sending = false;
			}
		);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			void send();
		}
	}

	// 최초 로드
	$effect(() => {
		void [token, projectId];
		untrack(() => {
			void loadConversations();
			void loadModels();
		});
	});

	// 메시지 변화 시 하단으로 스크롤
	$effect(() => {
		void messages.length;
		if (messages.length && messages[messages.length - 1]) {
			void messages[messages.length - 1].content;
		}
		const el = scrollEl;
		if (el) untrack(() => (el.scrollTop = el.scrollHeight));
	});
</script>

<Card padding="none" class="w-full h-[calc(100vh-8rem)] flex overflow-hidden">
	<!-- 사이드바: 모델 선택 + 대화 목록 -->
	<aside class="w-64 shrink-0 border-r border-[var(--color-line)] flex flex-col bg-[var(--color-surface-sunken)]">
		<div class="p-3 border-b border-[var(--color-line)] space-y-2">
			<Button onclick={newConversation} class="w-full">+ 새 대화</Button>
			<label class="block text-xs text-[var(--color-ink-3)]">
				모델
				<select
					bind:value={selectedModel}
					class="mt-1 w-full rounded-md border border-[var(--color-line)] bg-[var(--color-surface-base)] px-2 py-1.5 text-sm text-[var(--color-ink-1)]"
				>
					{#if models.length === 0}
						<option value="">모델 없음</option>
					{:else}
						{#each models as m (m.model_name)}
							<option value={m.model_name}>{m.display_name}</option>
						{/each}
					{/if}
				</select>
			</label>
		</div>
		<div class="flex-1 overflow-y-auto p-2 space-y-1">
			{#if conversations.length === 0}
				<p class="px-2 py-3 text-xs text-[var(--color-ink-3)]">대화가 없습니다</p>
			{:else}
				{#each conversations as conv (conv.id)}
					<button
						type="button"
						onclick={() => selectConversation(conv)}
						class="w-full truncate rounded-md px-3 py-2 text-left text-sm transition-colors
							{activeConvId === conv.id
							? 'bg-[var(--color-accent)] text-[var(--color-action-on-accent)]'
							: 'text-[var(--color-ink-2)] hover:bg-[var(--color-line)]/40'}"
					>
						{conv.title || '새 대화'}
					</button>
				{/each}
			{/if}
		</div>
	</aside>

	<!-- 메인: 메시지 + 입력 -->
	<section class="flex flex-1 flex-col min-w-0">
		<div bind:this={scrollEl} class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
			{#if messages.length === 0}
				<div class="flex h-full flex-col items-center justify-center gap-1 text-center">
					<p class="text-sm text-[var(--color-ink-2)]">무엇을 도와드릴까요?</p>
					<p class="text-xs text-[var(--color-ink-3)]">아래에 메시지를 입력해 대화를 시작하세요</p>
				</div>
			{:else}
				{#each messages as msg, i (i)}
					<div class="flex {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
						<div
							class="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2 text-sm
								{msg.role === 'user'
								? 'bg-[var(--color-accent)] text-[var(--color-action-on-accent)]'
								: 'bg-[var(--color-surface-sunken)] text-[var(--color-ink-1)]'}"
						>
							{msg.content}{#if msg.streaming}<span class="animate-pulse">▌</span>{/if}
						</div>
					</div>
				{/each}
			{/if}
		</div>

		{#if error}
			<div class="px-4 py-2 text-xs text-[var(--color-state-danger)]">{error}</div>
		{/if}

		<div class="border-t border-[var(--color-line)] p-3">
			<div class="flex items-end gap-2">
				<textarea
					bind:value={input}
					onkeydown={onKeydown}
					rows="1"
					placeholder="메시지를 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)"
					class="flex-1 resize-none rounded-md border border-[var(--color-line)] bg-[var(--color-surface-base)] px-3 py-2 text-sm text-[var(--color-ink-1)] focus:outline-none focus:border-[var(--color-accent)]"
				></textarea>
				<Button onclick={send} disabled={sending || !input.trim()}>
					{sending ? '전송 중…' : '전송'}
				</Button>
			</div>
		</div>
	</section>
</Card>
