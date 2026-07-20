<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import { streamChat, type ChatStreamEvent } from '$lib/api/chatStream';
	import {
		computeMetrics,
		estimateTokens,
		type StreamMetrics
	} from '$lib/api/chatMetrics';
	import type { ToolActivityItem } from '$lib/api/chatToolActivity';
	import { aggregateCitations } from '$lib/api/chatCitations';
	import { normalizeEffort } from '$lib/api/chatEffort';
	import { toRefs, type ChatAttachment } from '$lib/api/chatAttachments';
	import { SvelteMap } from 'svelte/reactivity';
	import {
		buildActivePath,
		lastAssistantModel,
		siblingLeafInDirection,
		type AvailableModel,
		type ChatUsage,
		type ChatMessage as ChatMsg
	} from '$lib/api/chatTree';
	import type { Agent } from '$lib/api/chatAgents';
	import type { Workspace, WorkspacePayload } from '$lib/api/chatWorkspaces';
	import ChatSidebar from './ChatSidebar.svelte';
	import ChatWindow from './ChatWindow.svelte';
	import ChatInput from './ChatInput.svelte';
	import ModelCapabilityBadges from './ModelCapabilityBadges.svelte';
	import AgentPicker from './AgentPicker.svelte';
	import AgentManagerModal from './AgentManagerModal.svelte';
	import AgentHubModal from './AgentHubModal.svelte';
	import ChatProjectsView from './ChatProjectsView.svelte';
	import ChatSettingsOverlay from './ChatSettingsOverlay.svelte';
	import ChatSourcesPanel from './ChatSourcesPanel.svelte';
	import ModelPickerOverlay from './ModelPickerOverlay.svelte';
	import ConversationWorkspacePicker from './ConversationWorkspacePicker.svelte';

	interface Conversation {
		id: string;
		title: string | null;
		model_name: string | null;
		workspace_id: number | null;
		active_leaf_id?: string | null;
		updated_at: string | null;
	}
	interface MessagesResponse {
		messages: ChatMsg[];
		active_leaf_id: string | null;
	}
	type DisplayMessage = ChatMsg & {
		streaming?: boolean;
		metrics?: StreamMetrics | null;
		toolItems?: ToolActivityItem[];
		reasoning?: string | null;
	};

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// --- 상태 ---
	let conversations = $state<Conversation[]>([]);
	let models = $state<AvailableModel[]>([]);
	let selectedModel = $state('');
	let effort = $state<string | null>(null); // thinking effort(null=서버 기본). reasoning 지원 모델만.
	let attachments = $state<ChatAttachment[]>([]); // 입력창 첨부(업로드 진행/완료)
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
	// 생성 속도(tok/s)는 저장하지 않는 런타임 계측값 — 이번 세션 동안 메시지 id 로 유지한다.
	// done 후 loadMessages 로 낙관적 draft 가 권위 메시지로 교체되면 새 리프 id 에 재부착한다.
	// SvelteMap: 일반 Map 은 $state 로 감싸도 .set() 이 반응성을 트리거하지 않는다(svelte/reactivity 필요).
	const metricsById = new SvelteMap<string, StreamMetrics>();

	// 에이전트: 바인딩은 클라이언트 상태(대화 객체에 저장되지 않음). 바인딩 중엔 에이전트가 모델을 소유.
	let agents = $state<Agent[]>([]);
	let activeAgent = $state<Agent | null>(null);
	let agentManagerOpen = $state(false);
	let agentHubOpen = $state(false);
	const modelLocked = $derived(activeAgent !== null);

	// 프로젝트(workspace) 관리 · 설정 오버레이
	let workspaces = $state<Workspace[]>([]);
	let view = $state<'chat' | 'projects'>('chat');
	let settingsOpen = $state(false);
	let sourcesOpen = $state(false);
	let modelPickerOpen = $state(false);

	// 현재 선택 모델의 능력(배지·게이팅). 에이전트 바인딩 시 에이전트 모델 기준.
	const activeModelName = $derived(activeAgent?.model_name || selectedModel);
	const selectedModelObj = $derived(models.find((m) => m.model_name === activeModelName) ?? null);

	// 모델을 바꾸면 현재 effort 가 새 모델에 없을 수 있으므로 정규화(없으면 null=서버 기본).
	$effect(() => {
		const normalized = normalizeEffort(effort, selectedModelObj?.capabilities);
		if (normalized !== effort) effort = normalized;
	});

	const _LAST_MODEL_KEY = 'chat:lastModel';
	function persistLastModel(name: string) {
		try {
			if (typeof localStorage !== 'undefined' && name) localStorage.setItem(_LAST_MODEL_KEY, name);
		} catch {
			/* localStorage 불가 환경 무시 */
		}
	}
	function chooseModel(name: string) {
		if (!name) return;
		selectedModel = name;
		persistLastModel(name);
	}

	// 사이드바 접기/펼치기 (데스크톱 토글 · 모바일 드로어). 모바일은 기본 접힘.
	let sidebarOpen = $state(true);
	function toggleSidebar() {
		sidebarOpen = !sidebarOpen;
	}
	function isMobile(): boolean {
		return typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches;
	}
	function closeSidebarOnMobile() {
		if (isMobile()) sidebarOpen = false;
	}
	// "이 프로젝트에서 새 채팅" → 다음 생성되는 대화를 이 프로젝트에 배정한다(생성 시 소비).
	let pendingWorkspaceId = $state<number | null>(null);

	// 스트리밍 중 화면에 얹는 낙관적 상태
	let stream = $state<{ base: DisplayMessage[]; assistant: DisplayMessage } | null>(null);
	let abortCtrl: AbortController | null = null;
	let tmpSeq = 0;

	const activePath = $derived(buildActivePath(allMessages, activeLeafId));
	const activeConv = $derived(conversations.find((c) => c.id === activeConvId) ?? null);

	// 현재 대화(또는 예약된 신규 대화)의 프로젝트. 입력창 위 선택기가 표시/변경.
	const currentWorkspaceId = $derived(activeConv?.workspace_id ?? pendingWorkspaceId);
	function changeConversationWorkspace(id: number | null) {
		if (activeConv) void assignWorkspace(activeConv, id);
		else pendingWorkspaceId = id; // 신규 대화 — 생성 시 배정
	}

	const displayPath = $derived.by((): DisplayMessage[] => {
		if (stream) return [...stream.base, stream.assistant];
		if (tempMode) return tempMessages;
		return activePath;
	});
	const isEmpty = $derived(displayPath.length === 0);
	const siblingSource = $derived(tempMode || stream ? [] : allMessages);
	// 대화 전체 출처(중복 제거) — 헤더 "출처" 버튼 + 패널 공유
	const allCitations = $derived(aggregateCitations(displayPath));

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
			streaming: true,
			toolItems: [],
			reasoning: ''
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
			if (!selectedModel && models.length) {
				// 새 채팅은 마지막에 선택한 모델로 시작(localStorage). 없으면 첫 모델.
				let last: string | null = null;
				try {
					last = typeof localStorage !== 'undefined' ? localStorage.getItem(_LAST_MODEL_KEY) : null;
				} catch {
					last = null;
				}
				selectedModel =
					last && models.some((m) => m.model_name === last) ? last : models[0].model_name;
			}
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

	async function loadAgents() {
		if (!token || !projectId) return;
		try {
			agents = await api.get<Agent[]>('/api/v1/chat/agents', token, projectId);
			// 바인딩된 에이전트가 삭제/변경됐으면 동기화
			if (activeAgent) {
				const fresh = agents.find((a) => a.id === activeAgent!.id);
				activeAgent = fresh ?? null;
			}
		} catch {
			/* 에이전트 로드 실패는 채팅 자체를 막지 않음 */
		}
	}

	async function loadWorkspaces() {
		if (!token || !projectId) return;
		try {
			workspaces = await api.get<Workspace[]>('/api/v1/chat/workspaces', token, projectId);
		} catch {
			/* 프로젝트 로드 실패는 채팅 자체를 막지 않음 */
		}
	}

	// --- 프로젝트(workspace) CRUD (프로젝트 뷰에서 호출) ---
	async function createWorkspace(payload: WorkspacePayload) {
		if (!token || !projectId) return;
		try {
			await api.post('/api/v1/chat/workspaces', payload, token, projectId);
			await loadWorkspaces();
			toast.success('프로젝트를 생성했습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장에 실패했습니다');
		}
	}
	async function updateWorkspace(id: number, payload: WorkspacePayload) {
		if (!token || !projectId) return;
		try {
			await api.patch(`/api/v1/chat/workspaces/${id}`, payload, token, projectId);
			await loadWorkspaces();
			toast.success('프로젝트를 수정했습니다');
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장에 실패했습니다');
		}
	}
	async function deleteWorkspace(w: Workspace): Promise<boolean> {
		if (!token || !projectId) return false;
		if (!(await confirmDialog(`'${w.name}' 프로젝트를 삭제하시겠습니까? 대화는 미분류로 이동합니다.`)))
			return false;
		try {
			await api.delete(`/api/v1/chat/workspaces/${w.id}`, token, projectId);
			await loadWorkspaces();
			await loadConversations();
			toast.success('삭제했습니다');
			return true;
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '삭제에 실패했습니다');
			return false;
		}
	}

	// 프로젝트 뷰에서 "이 프로젝트에서 새 채팅": 빈 대화로 초기화한 뒤 배정 대상만 예약.
	function newInProject(workspaceId: number) {
		newConversation(); // pending 초기화 + 뷰를 'chat'으로 복귀
		pendingWorkspaceId = workspaceId; // reset 이후에 설정해야 유실되지 않음
	}

	// 대화를 프로젝트에 배정/해제하고 로컬 목록을 낙관적으로 갱신(사이드바 재그룹핑).
	async function assignWorkspace(conv: Conversation, workspaceId: number | null) {
		if (!token || !projectId || conv.workspace_id === workspaceId) return;
		const prev = conv.workspace_id;
		conversations = conversations.map((c) =>
			c.id === conv.id ? { ...c, workspace_id: workspaceId } : c
		);
		try {
			await api.patch(
				`/api/v1/chat/conversations/${conv.id}/workspace`,
				{ workspace_id: workspaceId },
				token,
				projectId
			);
		} catch (e) {
			// 실패 시 롤백
			conversations = conversations.map((c) =>
				c.id === conv.id ? { ...c, workspace_id: prev } : c
			);
			error = e instanceof Error ? e.message : '프로젝트 배정에 실패했습니다';
		}
	}

	function bindAgent(agent: Agent) {
		activeAgent = agent;
		// 에이전트가 모델을 소유 → 상단 셀렉터에도 반영(모델이 목록에 있으면)
		if (agent.model_name && models.some((m) => m.model_name === agent.model_name)) {
			selectedModel = agent.model_name;
		}
	}
	function unbindAgent() {
		activeAgent = null;
	}

	// --- 대화 선택/생성 ---
	async function selectConversation(conv: Conversation) {
		if (streaming) return;
		view = 'chat';
		pendingWorkspaceId = null;
		tempMode = false;
		closeSidebarOnMobile();
		metricsById.clear(); // 런타임 tok/s 계측값은 대화 전환 시 초기화(누적 방지)
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
		view = 'chat';
		pendingWorkspaceId = null;
		tempMode = false;
		closeSidebarOnMobile();
		metricsById.clear();
		activeConvId = null;
		allMessages = [];
		activeLeafId = null;
		tempMessages = [];
		error = null;
	}
	function startTempChat() {
		if (streaming) return;
		view = 'chat';
		pendingWorkspaceId = null;
		closeSidebarOnMobile();
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
		// "이 프로젝트에서 새 채팅"으로 예약된 배정을 여기서 1회 소비한다.
		const wsId = pendingWorkspaceId;
		pendingWorkspaceId = null;
		if (wsId !== null) {
			try {
				await api.patch(
					`/api/v1/chat/conversations/${conv.id}/workspace`,
					{ workspace_id: wsId },
					token,
					projectId
				);
				conv.workspace_id = wsId;
			} catch {
				/* 배정 실패는 대화 생성 자체를 막지 않음 */
			}
		}
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
		onDone: (
			evt: Extract<ChatStreamEvent, { type: 'done' }>,
			metrics: StreamMetrics | null
		) => Promise<void> | void
	) {
		abortCtrl = new AbortController();
		// tok/s 계측: 첫 토큰 도착 시각(performance.now) + 누적 문자 수(라이브 근사).
		let firstTokenMs: number | null = null;
		let charCount = 0;
		try {
			for await (const evt of streamChat(path, body, {
				token,
				projectId,
				signal: abortCtrl.signal
			})) {
				if (evt.type === 'reasoning') {
					// 추론 델타 누적(저장 안 함, 라이브 노출)
					draft.reasoning = (draft.reasoning ?? '') + evt.text;
				} else if (evt.type === 'token') {
					toolActivity = null;
					if (firstTokenMs === null) firstTokenMs = performance.now();
					charCount += evt.text.length;
					draft.content += evt.text;
					// 라이브 근사치(문자→토큰) 갱신 — 완료 시 done 의 정확한 토큰으로 대체.
					draft.metrics = computeMetrics(
						estimateTokens(charCount),
						firstTokenMs,
						performance.now(),
						true
					);
				} else if (evt.type === 'tool_call') {
					toolActivity = evt.name;
				} else if (evt.type === 'tool_calls') {
					// 도구 호출(인자) → 실행 중 카드 추가
					const items = draft.toolItems ?? [];
					for (const c of evt.calls) {
						items.push({
							id: c.id ?? null,
							name: c.name,
							args: c.args ?? null,
							result: null,
							running: true
						});
					}
					draft.toolItems = items;
				} else if (evt.type === 'tool_result') {
					// 결과 → 매칭 카드 채우기(id 우선, 없으면 실행 중 동명 카드)
					const items = draft.toolItems ?? [];
					let target = evt.tool_call_id
						? items.find((t) => t.id && t.id === evt.tool_call_id)
						: undefined;
					if (!target) target = items.find((t) => t.running && t.name === evt.name);
					if (target) {
						target.result = evt.content;
						target.running = false;
					} else {
						items.push({
							id: evt.tool_call_id ?? null,
							name: evt.name,
							args: null,
							result: evt.content,
							running: false
						});
					}
					draft.toolItems = items;
					toolActivity = null;
				} else if (evt.type === 'citations') {
					// 출처 — 저장/재로딩과 동일 필드(message.citations)에 실어 하단·패널이 공유
					draft.citations = evt.items;
				} else if (evt.type === 'error') {
					error = evt.message || '모델 응답 중 오류가 발생했습니다';
					endStream();
					return;
				} else if (evt.type === 'done') {
					draft.streaming = false;
					// 확정 tok/s: done 이 준 completion_tokens 로 재계산(없으면 근사 유지).
					const finalMetrics =
						evt.completion_tokens != null
							? computeMetrics(evt.completion_tokens, firstTokenMs, performance.now(), false)
							: draft.metrics ?? null;
					draft.metrics = finalMetrics;
					await onDone(evt, finalMetrics);
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
		const atts = toRefs(attachments); // 완료된 첨부만 참조로
		attachments = []; // 전송과 함께 초기화

		if (tempMode) return sendTemp(text, atts);

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
			{
				message: text,
				model: selectedModel,
				agent_id: activeAgent?.id,
				reasoning_effort: effort,
				attachments: atts
			},
			live,
			async (_evt, metrics) => {
				await loadMessages(convId!);
				// 권위 트리 로드 후 새 assistant 리프(activeLeafId)에 계측값 재부착.
				if (metrics && activeLeafId) metricsById.set(activeLeafId, metrics);
				void loadConversations();
				void loadUsage();
			}
		);
	}

	async function sendTemp(text: string, atts: ReturnType<typeof toRefs> = []) {
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
			{ messages: payload, model: selectedModel, reasoning_effort: effort, attachments: atts },
			live,
			(_evt, metrics) => {
				// 임시 채팅은 저장되지 않으므로 완료된 답변을 로컬 배열에 확정(계측값 포함)
				tempMessages = [...history, { ...live, streaming: false, metrics }];
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
			{ model: modelName || undefined, agent_id: activeAgent?.id, reasoning_effort: effort },
			live,
			async (_evt, metrics) => {
				await loadMessages(activeConvId!);
				if (metrics && activeLeafId) metricsById.set(activeLeafId, metrics);
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

	// 최초 1회: 모바일이면 사이드바를 접은 상태로 시작(본문 우선 표시)
	$effect(() => {
		untrack(() => {
			if (isMobile()) sidebarOpen = false;
		});
	});

	// 최초 로드
	$effect(() => {
		void [token, projectId];
		untrack(() => {
			void loadConversations();
			void loadModels();
			void loadUsage();
			void loadAgents();
			void loadWorkspaces();
		});
	});
</script>

<div class="chat-shell">
	<ChatSidebar
		{conversations}
		{workspaces}
		{activeConvId}
		{tempMode}
		open={sidebarOpen}
		{usage}
		busy={streaming}
		onSelect={selectConversation}
		onNew={newConversation}
		onDelete={deleteConversation}
		onAssign={assignWorkspace}
		onAgents={() => (agentManagerOpen = true)}
		onWorkspaces={() => (view = 'projects')}
		onSettings={() => (settingsOpen = true)}
	/>

	<!-- 모바일 드로어 백드롭: 열렸을 때만 본문을 덮어 탭하면 닫힘 -->
	<button
		type="button"
		class="sidebar-backdrop"
		class:show={sidebarOpen}
		aria-label="사이드바 닫기"
		onclick={() => (sidebarOpen = false)}
	></button>

	<section class="main">
		{#if view === 'projects'}
			<ChatProjectsView
				{conversations}
				{workspaces}
				onCreate={createWorkspace}
				onUpdate={updateWorkspace}
				onDelete={deleteWorkspace}
				onAssign={assignWorkspace}
				onOpenConversation={selectConversation}
				onNewInProject={newInProject}
			/>
		{:else}
			<header class="head">
			<div class="head-left">
				<button type="button" class="sidebar-toggle" onclick={toggleSidebar} aria-label={sidebarOpen ? '사이드바 접기' : '사이드바 펼치기'} aria-expanded={sidebarOpen} title={sidebarOpen ? '사이드바 접기' : '사이드바 펼치기'}>
					<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round" /></svg>
				</button>
				{#if !sidebarOpen}
					<button type="button" class="sidebar-toggle" onclick={newConversation} disabled={streaming} title="새 채팅" aria-label="새 채팅">
						<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/if}
				<div class="head-title">
					{#if tempMode}
						임시 채팅
					{:else}
						{activeConv?.title || '새 채팅'}
					{/if}
				</div>
			</div>
			<div class="head-center">
				<div class="head-controls">
					<button
						type="button"
						class="model-btn"
						disabled={streaming || modelLocked}
						onclick={() => (modelPickerOpen = true)}
						title="모델 선택"
					>
						<span class="model-btn-name">{selectedModelObj?.display_name || activeModelName || '모델 선택'}</span>
						<ModelCapabilityBadges caps={selectedModelObj?.capabilities} size="xs" iconsOnly />
						<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
					<AgentPicker
						{agents}
						{activeAgent}
						disabled={streaming}
						onBind={bindAgent}
						onUnbind={unbindAgent}
						onManage={() => (agentManagerOpen = true)}
						onHub={() => (agentHubOpen = true)}
					/>
				</div>
				{#if modelLocked}
					<span class="model-lock-hint">모델은 에이전트가 제어합니다</span>
				{/if}
			</div>
			<div class="head-right">
				{#if allCitations.length}
					<button type="button" class="sources-btn" onclick={() => (sourcesOpen = true)} title="이 대화의 출처 보기">
						<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" stroke-linecap="round" stroke-linejoin="round" /></svg>
						출처 {allCitations.length}
					</button>
				{/if}
				<button
					type="button"
					class="temp-btn"
					class:active={tempMode}
					onclick={startTempChat}
					disabled={streaming}
					title="저장되지 않는 임시 채팅"
					aria-pressed={tempMode}
				>
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 8v4l2.5 2.5M12 3a9 9 0 1 0 9 9" stroke-linecap="round" stroke-linejoin="round" /></svg>
					<span class="temp-label">임시</span>
				</button>
			</div>
		</header>

		<ChatWindow
			activePath={displayPath}
			allMessages={siblingSource}
			{metricsById}
			{models}
			busy={streaming}
			loading={treeLoading}
			{modelLocked}
			{toolActivity}
			{error}
			empty={isEmpty}
			{tempMode}
			onCopy={copy}
			onRegenerate={regenerate}
			onFork={fork}
			onSwitchVersion={switchVersion}
		/>

		{#if !tempMode}
				<div class="composer-meta">
					<ConversationWorkspacePicker
						{workspaces}
						currentWorkspaceId={currentWorkspaceId}
						disabled={streaming}
						onChange={changeConversationWorkspace}
					/>
				</div>
			{/if}
			<ChatInput
				bind:value={input}
				bind:effort
				bind:attachments
				{token}
				{projectId}
				modelCaps={selectedModelObj?.capabilities}
				{streaming}
				onSend={send}
				onStop={stop}
			/>
		{/if}
	</section>
</div>

<AgentManagerModal
	open={agentManagerOpen}
	{models}
	onClose={() => (agentManagerOpen = false)}
	onChanged={loadAgents}
/>
<AgentHubModal open={agentHubOpen} onClose={() => (agentHubOpen = false)} onCloned={loadAgents} />
<ChatSettingsOverlay open={settingsOpen} onClose={() => (settingsOpen = false)} {usage} />
<ChatSourcesPanel open={sourcesOpen} citations={allCitations} onClose={() => (sourcesOpen = false)} />
<ModelPickerOverlay
	open={modelPickerOpen}
	{models}
	value={activeModelName}
	onSelect={chooseModel}
	onClose={() => (modelPickerOpen = false)}
/>

<style>
	.chat-shell {
		display: flex;
		height: calc(100vh - 3.5rem);
		width: 100%;
		overflow: hidden;
		background: var(--color-surface-base);
		position: relative; /* 모바일 드로어 사이드바·백드롭 기준 */
	}
	.sidebar-toggle {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 2rem;
		height: 2rem;
		margin-right: 0.4rem;
		border: none;
		border-radius: 0.45rem;
		background: transparent;
		color: var(--color-ink-2);
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
	}
	.sidebar-toggle:hover {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
	}
	.sidebar-backdrop {
		display: none;
		position: absolute;
		inset: 0;
		z-index: 39;
		border: none;
		padding: 0;
		background: color-mix(in oklab, var(--color-ink-0) 40%, transparent);
		opacity: 0;
		transition: opacity 0.2s ease;
		cursor: pointer;
	}
	/* 백드롭은 모바일에서 사이드바가 열렸을 때만 */
	@media (max-width: 768px) {
		.sidebar-backdrop.show {
			display: block;
			opacity: 1;
		}
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
		display: flex;
		align-items: center;
		min-width: 0;
	}
	.head-center {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		min-width: 0;
	}
	.head-controls {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
	}
	.model-lock-hint {
		font-size: 0.66rem;
		color: var(--color-ink-3);
	}
	.composer-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.3rem 1rem 0;
	}
	.model-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		max-width: 20rem;
		padding: 0.4rem 0.7rem;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-raised);
		color: var(--color-ink-0);
		font-size: 0.82rem;
		font-weight: 600;
		cursor: pointer;
		transition: border-color 0.15s, background 0.15s;
	}
	.model-btn:hover:not(:disabled) {
		border-color: var(--color-accent);
	}
	.model-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.model-btn-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.temp-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.35rem 0.65rem;
		border-radius: 0.55rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-raised);
		color: var(--color-ink-2);
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
		transition: background 0.15s, color 0.15s, border-color 0.15s;
	}
	.temp-btn:hover:not(:disabled) {
		color: var(--color-ink-0);
		border-color: var(--color-line-2);
	}
	.temp-btn.active {
		background: var(--color-accent);
		color: var(--color-action-on-accent);
		border-color: var(--color-accent);
	}
	.temp-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.head-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		justify-content: flex-end;
		min-width: 0;
	}
	.sources-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.3rem 0.6rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-raised);
		color: var(--color-ink-2);
		font-size: 0.72rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
	}
	.sources-btn:hover {
		border-color: var(--color-accent);
		color: var(--color-ink-0);
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
