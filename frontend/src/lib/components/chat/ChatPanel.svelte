<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { streamChat, type ChatStreamEvent } from '$lib/api/chatStream';
	import {
		buildActivePath,
		lastAssistantModel,
		siblingLeafInDirection,
		type AvailableModel,
		type ChatUsage,
		type ChatMessage as ChatMsg
	} from '$lib/api/chatTree';
	import ChatSidebar from './ChatSidebar.svelte';
	import ChatWindow from './ChatWindow.svelte';
	import ChatInput from './ChatInput.svelte';
	import ModelSelector from './ModelSelector.svelte';
	import ChatUsageWidget from './ChatUsageWidget.svelte';

	interface Conversation {
		id: string;
		title: string | null;
		model_name: string | null;
		active_leaf_id?: string | null;
		updated_at: string | null;
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
	let treeLoading = $state(false); // 분기/재생성 대상 전환 등 트리 재조회 중
	let usage = $state<ChatUsage | null>(null);

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
		syncSelectedModel();
	}

	// 활성 경로의 마지막 assistant 모델을 상단 셀렉터에 반영한다.
	// select/switch/regenerate-done/fork 모두 loadMessages 를 지나므로 여기 단일 지점에 둔다.
	// 단, 현재 등록된 models 목록에 존재하는 모델일 때만 반영(삭제/이름변경 모델로 셀렉터가 깨지지 않게).
	function syncSelectedModel() {
		const m = lastAssistantModel(buildActivePath(allMessages, activeLeafId));
		if (m && models.some((x) => x.model_name === m)) selectedModel = m;
	}

	async function loadUsage() {
		if (!token || !projectId) return;
		try {
			usage = await api.get<ChatUsage>('/api/v1/chat/usage', token, projectId);
		} catch {
			/* 사용량 위젯은 실패해도 채팅에 영향 없음 */
		}
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
				void loadUsage();
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
				void loadUsage();
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
				void loadUsage();
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
		treeLoading = true;
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
		} finally {
			treeLoading = false;
		}
	}

	// --- 분기 ---
	async function fork(messageId: string) {
		if (streaming || tempMode || !activeConvId || !token || !projectId) return;
		treeLoading = true;
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
		} finally {
			treeLoading = false;
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
			void loadUsage();
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
			<div class="head-left">
				<div class="head-title">
					{#if tempMode}
						임시 채팅
					{:else}
						{activeConv?.title || '새 채팅'}
					{/if}
				</div>
			</div>
			<div class="head-center">
				<ModelSelector {models} value={selectedModel} onSelect={(m) => (selectedModel = m)} align="center" searchable />
			</div>
			<div class="head-right">
				{#if usage}
					<ChatUsageWidget {usage} />
				{/if}
			</div>
		</header>

		<ChatWindow
			activePath={displayPath}
			allMessages={siblingSource}
			{models}
			busy={streaming}
			loading={treeLoading}
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
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: 1rem;
		padding: 0.7rem 1rem;
		border-bottom: 1px solid var(--color-line);
		background: var(--color-surface-base);
	}
	.head-left {
		min-width: 0;
	}
	.head-center {
		display: flex;
		justify-content: center;
		min-width: 0;
	}
	.head-right {
		display: flex;
		justify-content: flex-end;
		min-width: 0;
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
