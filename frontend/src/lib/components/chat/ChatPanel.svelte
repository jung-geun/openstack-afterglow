<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { streamChat, type ChatStreamEvent } from '$lib/api/chatStream';
	import {
		buildActivePath,
		siblingLeafInDirection,
		type ChatMessage as ChatMsg
	} from '$lib/api/chatTree';
	import ChatSidebar from './ChatSidebar.svelte';
	import ChatWindow from './ChatWindow.svelte';
	import ChatInput from './ChatInput.svelte';
	import ModelSelector from './ModelSelector.svelte';

	interface Conversation {
		id: string;
		title: string | null;
		model_name: string | null;
		active_leaf_id?: string | null;
		updated_at: string | null;
	}
	interface AvailableModel {
		model_name: string;
		display_name: string;
	}
	interface MessagesResponse {
		messages: ChatMsg[];
		active_leaf_id: string | null;
	}
	type DisplayMessage = ChatMsg & { streaming?: boolean };

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// --- 상태 ---
	let conversations = $state<Conversation[]>([]);
	let models = $state<AvailableModel[]>([]);
	let selectedModel = $state('');
	let activeConvId = $state<string | null>(null);
	let allMessages = $state<ChatMsg[]>([]);
	let activeLeafId = $state<string | null>(null);
	let input = $state('');
	let error = $state<string | null>(null);
	let toolActivity = $state<string | null>(null);
	let streaming = $state(false);
	let tempMode = $state(false);
	let tempMessages = $state<DisplayMessage[]>([]);

	// 스트리밍 중 화면에 얹는 낙관적 상태
	let stream = $state<{ base: DisplayMessage[]; assistant: DisplayMessage } | null>(null);
	let abortCtrl: AbortController | null = null;
	let tmpSeq = 0;

	const activePath = $derived(buildActivePath(allMessages, activeLeafId));
	const activeConv = $derived(conversations.find((c) => c.id === activeConvId) ?? null);

	const displayPath = $derived.by((): DisplayMessage[] => {
		if (stream) return [...stream.base, stream.assistant];
		if (tempMode) return tempMessages;
		return activePath;
	});
	const isEmpty = $derived(displayPath.length === 0);
	const siblingSource = $derived(tempMode || stream ? [] : allMessages);

	function tempId(): string {
		return `tmp-${tmpSeq++}`;
	}
	function newAssistantDraft(model: string | null): DisplayMessage {
		return {
			id: tempId(),
			conversation_id: activeConvId ?? '',
			role: 'assistant',
			parent_id: null,
			content: '',
			model_name: model,
			created_at: null,
			streaming: true
		};
	}

	// --- 로딩 ---
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
		const res = await api.get<MessagesResponse>(
			`/api/v1/chat/conversations/${convId}/messages`,
			token,
			projectId
		);
		allMessages = res.messages ?? [];
		activeLeafId = res.active_leaf_id ?? null;
	}

	// --- 대화 선택/생성 ---
	async function selectConversation(conv: Conversation) {
		if (streaming) return;
		tempMode = false;
		activeConvId = conv.id;
		if (conv.model_name) selectedModel = conv.model_name;
		error = null;
		try {
			await loadMessages(conv.id);
		} catch (e) {
			error = e instanceof Error ? e.message : '메시지를 불러오지 못했습니다';
		}
	}
	function newConversation() {
		if (streaming) return;
		tempMode = false;
		activeConvId = null;
		allMessages = [];
		activeLeafId = null;
		tempMessages = [];
		error = null;
	}
	function startTempChat() {
		if (streaming) return;
		tempMode = true;
		activeConvId = null;
		allMessages = [];
		activeLeafId = null;
		tempMessages = [];
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

	// --- 스트리밍 공통 ---
	function endStream() {
		streaming = false;
		toolActivity = null;
		stream = null;
		abortCtrl = null;
	}

	async function runStream(
		path: string,
		body: unknown,
		draft: DisplayMessage,
		onDone: (evt: Extract<ChatStreamEvent, { type: 'done' }>) => Promise<void> | void
	) {
		abortCtrl = new AbortController();
		try {
			for await (const evt of streamChat(path, body, {
				token,
				projectId,
				signal: abortCtrl.signal
			})) {
				if (evt.type === 'token') {
					toolActivity = null;
					draft.content += evt.text;
				} else if (evt.type === 'tool_call') {
					toolActivity = evt.name;
				} else if (evt.type === 'error') {
					error = evt.message || '모델 응답 중 오류가 발생했습니다';
					endStream();
					return;
				} else if (evt.type === 'done') {
					draft.streaming = false;
					await onDone(evt);
					endStream();
					return;
				}
			}
			// done 없이 스트림이 닫힌 경우
			endStream();
		} catch (e) {
			if ((e as Error)?.name === 'AbortError') {
				// 사용자가 중단: 지금까지의 낙관적 내용은 버리고 권위 트리로 복구
				if (!tempMode && activeConvId) {
					try {
						await loadMessages(activeConvId);
					} catch {
						/* ignore */
					}
				}
				endStream();
				return;
			}
			error = e instanceof Error ? e.message : '스트리밍 중 오류가 발생했습니다';
			endStream();
		}
	}

	// --- 전송 ---
	async function send() {
		const text = input.trim();
		if (!text || streaming || !token || !projectId) return;
		if (!selectedModel) {
			error = '사용 가능한 모델이 없습니다. 관리자에게 문의하세요.';
			return;
		}
		error = null;
		input = '';

		if (tempMode) return sendTemp(text);

		streaming = true;
		let convId: string | null;
		try {
			convId = await ensureConversation(text);
		} catch (e) {
			error = e instanceof Error ? e.message : '대화를 생성하지 못했습니다';
			endStream();
			return;
		}
		if (!convId) {
			endStream();
			return;
		}

		const userMsg: DisplayMessage = {
			id: tempId(),
			conversation_id: convId,
			role: 'user',
			parent_id: activeLeafId,
			content: text,
			created_at: null
		};
		stream = { base: [...activePath, userMsg], assistant: newAssistantDraft(selectedModel) };
		// $state 프록시를 경유해 mutate 해야 반응성이 발생한다(raw draft 직접 쓰기는 트랩 우회).
		const live = stream.assistant;

		await runStream(
			`/api/v1/chat/conversations/${convId}/completions`,
			{ message: text, model: selectedModel },
			live,
			async () => {
				await loadMessages(convId!);
				void loadConversations();
			}
		);
	}

	async function sendTemp(text: string) {
		const userMsg: DisplayMessage = {
			id: tempId(),
			conversation_id: '',
			role: 'user',
			parent_id: null,
			content: text,
			created_at: null
		};
		const history = [...tempMessages, userMsg];
		tempMessages = history;
		streaming = true;
		stream = { base: history, assistant: newAssistantDraft(selectedModel) };
		const live = stream.assistant; // 프록시 경유(반응성)

		const payload = history.map((m) => ({ role: m.role, content: m.content }));
		await runStream(
			'/api/v1/chat/temp-completions',
			{ messages: payload, model: selectedModel },
			live,
			() => {
				// 임시 채팅은 저장되지 않으므로 완료된 답변을 로컬 배열에 확정
				tempMessages = [...history, { ...live, streaming: false }];
			}
		);
	}

	// --- 재생성 ---
	async function regenerate(messageId: string, modelName: string) {
		if (streaming || tempMode || !activeConvId || !token || !projectId) return;
		error = null;
		const idx = activePath.findIndex((m) => m.id === messageId);
		if (idx === -1) return;
		streaming = true;
		stream = { base: activePath.slice(0, idx), assistant: newAssistantDraft(modelName || selectedModel) };
		const live = stream.assistant; // 프록시 경유(반응성)

		await runStream(
			`/api/v1/chat/conversations/${activeConvId}/messages/${messageId}/regenerate`,
			{ model: modelName || undefined },
			live,
			async () => {
				await loadMessages(activeConvId!);
				void loadConversations();
			}
		);
	}

	// --- 버전 전환 ---
	async function switchVersion(messageId: string, direction: -1 | 1) {
		if (streaming || tempMode || !activeConvId || !token || !projectId) return;
		const msg = allMessages.find((m) => m.id === messageId);
		if (!msg) return;
		const targetLeaf = siblingLeafInDirection(allMessages, msg, direction);
		if (!targetLeaf) return;
		try {
			await api.patch(
				`/api/v1/chat/conversations/${activeConvId}/active-leaf`,
				{ message_id: targetLeaf },
				token,
				projectId
			);
			activeLeafId = targetLeaf; // 낙관적
			await loadMessages(activeConvId);
		} catch (e) {
			error = e instanceof Error ? e.message : '버전 전환에 실패했습니다';
		}
	}

	// --- 분기 ---
	async function fork(messageId: string) {
		if (streaming || tempMode || !activeConvId || !token || !projectId) return;
		try {
			const conv = await api.post<Conversation>(
				`/api/v1/chat/conversations/${activeConvId}/fork`,
				{ message_id: messageId },
				token,
				projectId
			);
			conversations = [conv, ...conversations];
			await selectConversation(conv);
		} catch (e) {
			error = e instanceof Error ? e.message : '분기에 실패했습니다';
		}
	}

	// --- 삭제 ---
	async function deleteConversation(conv: Conversation) {
		if (streaming || !token || !projectId) return;
		try {
			await api.delete(`/api/v1/chat/conversations/${conv.id}`, token, projectId);
			conversations = conversations.filter((c) => c.id !== conv.id);
			if (activeConvId === conv.id) newConversation();
		} catch (e) {
			error = e instanceof Error ? e.message : '삭제에 실패했습니다';
		}
	}

	function stop() {
		abortCtrl?.abort();
	}
	function copy(text: string) {
		void navigator.clipboard?.writeText(text);
	}

	// 최초 로드
	$effect(() => {
		void [token, projectId];
		untrack(() => {
			void loadConversations();
			void loadModels();
		});
	});
</script>

<div class="chat-shell">
	<ChatSidebar
		{conversations}
		{activeConvId}
		{tempMode}
		busy={streaming}
		onSelect={selectConversation}
		onNew={newConversation}
		onTempChat={startTempChat}
		onDelete={deleteConversation}
	/>

	<section class="main">
		<header class="head">
			<div class="head-title">
				{#if tempMode}
					임시 채팅
				{:else}
					{activeConv?.title || '새 채팅'}
				{/if}
			</div>
			<ModelSelector {models} value={selectedModel} onSelect={(m) => (selectedModel = m)} align="right" />
		</header>

		<ChatWindow
			activePath={displayPath}
			allMessages={siblingSource}
			{models}
			busy={streaming}
			{toolActivity}
			{error}
			empty={isEmpty}
			{tempMode}
			onCopy={copy}
			onRegenerate={regenerate}
			onFork={fork}
			onSwitchVersion={switchVersion}
		/>

		<ChatInput bind:value={input} {streaming} onSend={send} onStop={stop} />
	</section>
</div>

<style>
	.chat-shell {
		display: flex;
		height: calc(100vh - 3.5rem);
		width: 100%;
		overflow: hidden;
		background: var(--color-surface-base);
	}
	.main {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		min-height: 0;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.7rem 1rem;
		border-bottom: 1px solid var(--color-line);
		background: var(--color-surface-base);
	}
	.head-title {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--color-ink-0);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
