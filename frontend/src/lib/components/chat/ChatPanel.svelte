<script lang="ts">
	import { goto } from '$app/navigation';
	import { onDestroy, onMount, tick, untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import {
		cancelChatRun,
		createChatRun,
		followChatRun,
		parseChatRunDescriptor,
		type ChatRunDescriptor
	} from '$lib/api/chatStream';
	import { createRunViewState, reduceRunEvent } from '$lib/api/chatRunReducer';
	import {
		computeMetrics,
		estimateTokens,
		type StreamMetrics
	} from '$lib/api/chatMetrics';
	import type { ToolActivityItem } from '$lib/api/chatToolActivity';
	import { aggregateCitations } from '$lib/api/chatCitations';
	import { normalizeEffort } from '$lib/api/chatEffort';
	import { createChatRevealBuffer } from '$lib/api/chatRevealBuffer';
	import { createChatRunAttachment } from '$lib/api/chatRunAttachment';
	import {
		clearActiveConversationId,
		loadActiveConversationId,
		saveActiveConversationId
	} from '$lib/api/chatSession';
	import { toInputParts, type ChatAttachment } from '$lib/api/chatAttachments';
	import { defaultChatFeatureOptions, type UserInputPart } from '$lib/api/chatContracts';
	import { SvelteMap } from 'svelte/reactivity';
	import {
		buildActivePath,
		lastAssistantModel,
		siblingLeafInDirection,
		type AvailableModel,
		type ChatUsage,
		type ChatMessage as ChatMsg,
		type ChatTreeNode
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
	import CreateProjectDialog from './CreateProjectDialog.svelte';
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
		tree_nodes: ChatTreeNode[];
		active_leaf_id: string | null;
		has_more: boolean;
		next_before_id: string | null;
	}
	type DisplayMessage = ChatMsg & {
		streaming?: boolean;
		metrics?: StreamMetrics | null;
		toolItems?: ToolActivityItem[];
		reasoning?: string | null;
	};

	type AgentActivity = {
		label: string;
		startedAt: string;
	};

	function activityForRunStage(
		stage: 'queued' | 'model_request' | 'model_response' | 'tool_execution' | 'response_writing' | 'finalizing',
		startedAt: string,
		toolName: string | null
	): AgentActivity {
		const label = {
			queued: '실행 대기열에 등록되었습니다',
			model_request: '모델에 작업을 요청하는 중입니다',
			model_response: '모델 응답을 처리하는 중입니다',
			tool_execution: `${toolName} 도구를 실행 중입니다`,
			response_writing: '응답을 작성하는 중입니다',
			finalizing: '응답을 저장하는 중입니다'
		}[stage];
		return { label, startedAt };
	}


	interface Props {
		/** Undefined is the normal chat route; null is the project index. */
		projectRoute?: number | null;
		/** One-shot workspace assignment for a newly created conversation. */
		initialWorkspaceId?: number | null;
	}
	let { projectRoute = undefined, initialWorkspaceId = null }: Props = $props();
	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// --- 상태 ---
	let conversations = $state<Conversation[]>([]);
	let models = $state<AvailableModel[]>([]);
	let selectedModel = $state('');
	let effort = $state('auto'); // auto=provider 기본, none=명시적 비활성.
	let attachments = $state<ChatAttachment[]>([]); // 입력창 첨부(업로드 진행/완료)
	// 대화별 tool/MCP 선택 — null=활성 전체(기본), 배열=해당 항목만. (에이전트 바인딩 시 에이전트가 소유)
	let availableTools = $state<{ id: number; name: string }[]>([]);
	let availableMcp = $state<{ id: number; name: string }[]>([]);
	let availableSkills = $state<{ id: number; name: string }[]>([]);
	let selectedToolIds = $state<number[] | null>(null);
	let selectedMcpIds = $state<number[] | null>(null);
	// 스킬은 opt-in — 기본 미선택([]), 선택된 것만 주입.
	let selectedSkillIds = $state<number[]>([]);
	let composerAnchor = $state<HTMLDivElement | null>(null);

	let activeConvId = $state<string | null>(null);

	function selectedFeatureOptions() {
		const features = defaultChatFeatureOptions();
		features.tool_policy.enabled_tool_ids =
			selectedToolIds === null ? null : selectedToolIds.map(String);
		return features;
	}
	let selectionGeneration = 0;
	let restoredConversationProjectId: string | null = null;
	let allMessages = $state<ChatMsg[]>([]);
	let activeLeafId = $state<string | null>(null);
	let input = $state('');
	let error = $state<string | null>(null);
	let toolActivity = $state<string | null>(null);
	let agentActivity = $state<AgentActivity | null>(null);
	let streaming = $state(false);
	let runningConversationIds = $state<Set<string>>(new Set());
	let treeNodes = $state<ChatTreeNode[]>([]);
	let tempMode = $state(false);
	let tempMessages = $state<DisplayMessage[]>([]);
	let treeLoading = $state(false); // 분기/재생성 대상 전환 등 트리 재조회 중
	let historyLoading = $state(false);
	let historyHasMore = $state(false);
	let historyBeforeId = $state<string | null>(null);
	let usage = $state<ChatUsage | null>(null);
	// 생성 속도(tok/s)는 저장하지 않는 런타임 계측값 — 이번 세션 동안 메시지 id 로 유지한다.
	// done 후 loadMessages 로 낙관적 draft 가 권위 메시지로 교체되면 새 리프 id 에 재부착한다.
	// SvelteMap: 일반 Map 은 $state 로 감싸도 .set() 이 반응성을 트리거하지 않는다(svelte/reactivity 필요).
	const metricsById = new SvelteMap<string, StreamMetrics>();


	function setConversationRun(conversationId: string, running: boolean) {
		const next = new Set(runningConversationIds);
		if (running) next.add(conversationId);
		else next.delete(conversationId);
		runningConversationIds = next;
	}
	// 에이전트: 바인딩은 클라이언트 상태(대화 객체에 저장되지 않음). 바인딩 중엔 에이전트가 모델을 소유.
	let agents = $state<Agent[]>([]);
	let activeAgent = $state<Agent | null>(null);
	let agentManagerOpen = $state(false);
	let agentHubOpen = $state(false);
	const modelLocked = $derived(activeAgent !== null);

	// 프로젝트(workspace) 관리 · 설정 오버레이
	let workspaces = $state<Workspace[]>([]);
	let view = $state<'chat' | 'projects'>('chat');
	let projectsInitialMode = $state<'grid'>('grid');
	let projectsInitialWorkspaceId = $state<number | null>(null);
	let createProjectDialogOpen = $state(false);
	let settingsOpen = $state(false);
	let sourcesOpen = $state(false);
	let modelPickerOpen = $state(false);

	$effect(() => {
		if (projectRoute === undefined) return;
		view = 'projects';
		projectsInitialWorkspaceId = projectRoute;
	});

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

	// 스트리밍 중 화면에 얹는 낙관적 상태. worker는 화면 전환과 무관하게 계속 실행된다.
	$effect(() => {
		if (initialWorkspaceId !== null && activeConvId === null && !tempMode) {
			pendingWorkspaceId = initialWorkspaceId;
		}
	});
	let stream = $state<{
		base: DisplayMessage[];
		assistant: DisplayMessage;
		conversationId: string | null;
		temp: boolean;
	} | null>(null);
	let currentRun = $state<ChatRunDescriptor | null>(null);
	let tempThreadId = $state<string | null>(null);
	let tmpSeq = 0;
	let streamGeneration = 0;
	let destroyed = false;
	const revealFrames = new Set<number>();
	const streamAttachment = createChatRunAttachment();

	onDestroy(() => {
		destroyed = true;
		for (const frame of revealFrames) cancelAnimationFrame(frame);
		streamAttachment.detach();
	});

	onMount(() => {
		const reconcile = () => {
			void refreshServerRunSnapshot();
			if (activeConvId && !tempMode && !currentRun) void resumeActiveRun(activeConvId);
		};
		window.addEventListener('focus', reconcile);
		window.addEventListener('online', reconcile);
		return () => {
			window.removeEventListener('focus', reconcile);
			window.removeEventListener('online', reconcile);
		};
	});

	/** Detach this view from a durable run. This intentionally never sends a cancel request. */
	function detachLocalStream() {
		streamGeneration = streamAttachment.detach();
		for (const frame of revealFrames) cancelAnimationFrame(frame);
		revealFrames.clear();
		streaming = false;
		toolActivity = null;
		agentActivity = null;
		stream = null;
		currentRun = null;
	}

	const activePath = $derived(buildActivePath(allMessages, activeLeafId));
	const activeConv = $derived(conversations.find((c) => c.id === activeConvId) ?? null);

	// 현재 대화(또는 예약된 신규 대화)의 프로젝트. 입력창 위 선택기가 표시/변경.
	const currentWorkspaceId = $derived(activeConv?.workspace_id ?? pendingWorkspaceId);
	const _TEMP_THREAD_KEY = 'chat:tempThreadId';

	function rememberTempThread(id: string | null) {
		tempThreadId = id;
		try {
			if (id) sessionStorage.setItem(_TEMP_THREAD_KEY, id);
			else sessionStorage.removeItem(_TEMP_THREAD_KEY);
		} catch {
			// Temporary chat remains usable when browser storage is unavailable.
		}
	}

	function changeConversationWorkspace(id: number | null) {
		if (activeConv) void assignWorkspace(activeConv, id);
		else pendingWorkspaceId = id; // 신규 대화 — 생성 시 배정
	}
	function openProjects() {
		void goto('/dashboard/chat/projects');
	}
	function createProject() {
		createProjectDialogOpen = true;
	}
	async function createProjectFromDialog(name: string): Promise<boolean> {
		return createWorkspace({ name });
	}
	function openProjectWorkspace(workspaceId: number) {
		void goto(`/dashboard/chat/projects/${workspaceId}`);
	}
	function leaveProjectsRoute() {
		if (projectRoute !== undefined) void goto('/dashboard/chat');
	}
	function navigateProjectRoute(workspaceId: number | null) {
		if (workspaceId === null) void goto('/dashboard/chat/projects');
		else openProjectWorkspace(workspaceId);
	}

	const displayPath = $derived.by(() => {
		if (stream && (stream.temp ? tempMode : stream.conversationId === activeConvId)) {
			return [...stream.base, stream.assistant];
		}
		if (tempMode) return tempMessages;
		return activePath;
	});
	const isEmpty = $derived(displayPath.length === 0);
	$effect.pre(() => {
		const emptyBefore = isEmpty;
		const before = composerAnchor?.getBoundingClientRect().top;
		void tick().then(() => {
			if (
				emptyBefore === isEmpty ||
				before === undefined ||
				composerAnchor === null ||
				window.matchMedia('(prefers-reduced-motion: reduce)').matches
			)
				return;
			const delta = before - composerAnchor.getBoundingClientRect().top;
			if (Math.abs(delta) > 1) {
				composerAnchor.animate(
					[
						{ transform: `translateY(${delta}px)` },
						{ transform: 'translateY(0)' }
					],
					{ duration: 240, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
				);
			}
		});
	});
	const treeSource = $derived(tempMode || (stream && stream.conversationId === activeConvId) ? [] : treeNodes);
	const tempToggleLocked = $derived(streaming || activeConvId !== null || tempMessages.length > 0);
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
	async function refreshServerRunSnapshot(): Promise<ChatRunDescriptor[]> {
		if (!token || !projectId) return [];
		try {
			const payload = await api.get<unknown[]>('/api/v1/chat/runs?active=true', token, projectId);
			const runs = payload.map(parseChatRunDescriptor);
			runningConversationIds = new Set(
				runs.flatMap((run) => (run.conversation_id ? [run.conversation_id] : []))
			);
			return runs;
		} catch {
			// A transient snapshot failure must not block loading durable history.
			return [];
		}
	}

	async function loadConversations() {
		if (!token || !projectId) return;
		try {
			const loaded = await api.get<Conversation[]>('/api/v1/chat/conversations', token, projectId);
			conversations = loaded;
			const activeRuns = await refreshServerRunSnapshot();
			if (projectRoute !== undefined || initialWorkspaceId !== null) {
				if (initialWorkspaceId !== null) clearActiveConversationId(projectId);
				return;
			}
			if (restoredConversationProjectId === projectId) return;
			restoredConversationProjectId = projectId;
			const savedId = loadActiveConversationId(projectId);
			const savedConversation = savedId ? loaded.find((conversation) => conversation.id === savedId) : undefined;
			const activeConversation = activeRuns
				.map((run) => (run.conversation_id ? loaded.find((conversation) => conversation.id === run.conversation_id) : undefined))
				.find((conversation): conversation is Conversation => Boolean(conversation));
			const conversation = savedConversation ?? activeConversation;
			if (conversation) void selectConversation(conversation);
			else if (savedId) clearActiveConversationId(projectId);
		} catch (e) {
			error = e instanceof Error ? e.message : '대화 목록을 불러오지 못했습니다';
		}
	}
	async function searchConversations(query: string): Promise<Conversation[]> {
		if (!token || !projectId) return [];
		const params = new URLSearchParams({ q: query, limit: '20' });
		return api.get<Conversation[]>(`/api/v1/chat/conversations/search?${params}`, token, projectId);
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
	async function loadMessages(convId: string, selection = selectionGeneration): Promise<boolean> {
		if (!token || !projectId) return false;
		const res = await api.get<MessagesResponse>(
			`/api/v1/chat/conversations/${convId}/messages?limit=40`,
			token,
			projectId
		);
		if (
			destroyed ||
			selection !== selectionGeneration ||
			tempMode ||
			activeConvId !== convId
		)
			return false;
		allMessages = res.messages ?? [];
		treeNodes = res.tree_nodes ?? [];
		activeLeafId = res.active_leaf_id ?? null;
		historyHasMore = Boolean(res.has_more);
		historyBeforeId = res.next_before_id ?? null;
		syncSelectedModel();
		return true;
	}

	async function loadOlderMessages(): Promise<void> {
		const convId = activeConvId;
		const beforeId = historyBeforeId;
		if (!token || !projectId || !convId || !beforeId || !historyHasMore || historyLoading) return;
		const selection = selectionGeneration;
		historyLoading = true;
		try {
			const params = new URLSearchParams({ limit: '40', before_id: String(beforeId) });
			const res = await api.get<MessagesResponse>(
				`/api/v1/chat/conversations/${convId}/messages?${params}`,
				token,
				projectId
			);
			if (destroyed || selection !== selectionGeneration || activeConvId !== convId || tempMode) return;
			const seen = new Set(allMessages.map((message) => String(message.id)));
			allMessages = [...(res.messages ?? []).filter((message) => !seen.has(String(message.id))), ...allMessages];
			historyHasMore = Boolean(res.has_more);
			if (res.tree_nodes?.length) treeNodes = res.tree_nodes;
			historyBeforeId = res.next_before_id ?? null;
		} finally {
			if (!destroyed && selection === selectionGeneration && activeConvId === convId) historyLoading = false;
		}
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
	async function loadToolsAndMcp() {
		if (!token || !projectId) return;
		try {
			availableTools = await api.get<{ id: number; name: string }[]>(
				'/api/v1/chat/custom-tools',
				token,
				projectId
			);
		} catch {
			availableTools = [];
		}
		try {
			availableMcp = await api.get<{ id: number; name: string }[]>(
				'/api/v1/chat/mcp-servers',
				token,
				projectId
			);
		} catch {
			availableMcp = [];
		}
		try {
			availableSkills = await api.get<{ id: number; name: string }[]>(
				'/api/v1/chat/skills',
				token,
				projectId
			);
		} catch {
			availableSkills = [];
		}
	}

	// --- 프로젝트(workspace) CRUD (프로젝트 뷰에서 호출) ---
	async function createWorkspace(payload: WorkspacePayload): Promise<boolean> {
		if (!token || !projectId) return false;
		try {
			await api.post('/api/v1/chat/workspaces', payload, token, projectId);
			await loadWorkspaces();
			toast.success('프로젝트를 생성했습니다');
			return true;
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장에 실패했습니다');
			return false;
		}
	}
	async function updateWorkspace(id: number, payload: WorkspacePayload): Promise<boolean> {
		if (!token || !projectId) return false;
		try {
			await api.patch(`/api/v1/chat/workspaces/${id}`, payload, token, projectId);
			await loadWorkspaces();
			toast.success('프로젝트를 수정했습니다');
			return true;
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장에 실패했습니다');
			return false;
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

	// 프로젝트 뷰에서 새 채팅으로 전환할 때 assignment를 URL로 전달해 새 route instance에도 보존한다.
	function newInProject(workspaceId: number) {
		void goto(`/dashboard/chat?workspace=${workspaceId}`);
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
		leaveProjectsRoute();
		detachLocalStream();
		const selection = ++selectionGeneration;
		view = 'chat';
		pendingWorkspaceId = null;
		tempMode = false;
		historyHasMore = false;
		historyBeforeId = null;
		historyLoading = false;
		closeSidebarOnMobile();
		metricsById.clear(); // 런타임 tok/s 계측값은 대화 전환 시 초기화(누적 방지)
		treeNodes = [];
		activeConvId = conv.id;
		if (projectId) saveActiveConversationId(projectId, conv.id);
		if (conv.model_name) selectedModel = conv.model_name;
		error = null;
		try {
			if (await loadMessages(conv.id, selection)) void resumeActiveRun(conv.id);
		} catch (e) {
			if (selection === selectionGeneration && activeConvId === conv.id) {
				error = e instanceof Error ? e.message : '메시지를 불러오지 못했습니다';
			}
		}
	}
	function newConversation() {
		leaveProjectsRoute();
		detachLocalStream();
		selectionGeneration += 1;
		view = 'chat';
		pendingWorkspaceId = null;
		tempMode = false;
		historyHasMore = false;
		historyBeforeId = null;
		historyLoading = false;
		closeSidebarOnMobile();
		metricsById.clear();
		activeConvId = null;
		if (projectId) clearActiveConversationId(projectId);
		allMessages = [];
		treeNodes = [];
		activeLeafId = null;
		tempMessages = [];
		error = null;
	}
	function toggleTempChat() {
		if (tempToggleLocked) return;
		if (tempMode) {
			tempMode = false;
			rememberTempThread(null);
			return;
		}
		leaveProjectsRoute();
		detachLocalStream();
		selectionGeneration += 1;
		view = 'chat';
		pendingWorkspaceId = null;
		closeSidebarOnMobile();
		tempMode = true;
		historyHasMore = false;
		historyBeforeId = null;
		historyLoading = false;
		rememberTempThread(null);
		if (projectId) clearActiveConversationId(projectId);
		activeConvId = null;
		allMessages = [];
		treeNodes = [];
		activeLeafId = null;
		tempMessages = [];
		error = null;
	}
	async function ensureConversation(firstMessage: string): Promise<string | null> {
		if (activeConvId) return activeConvId;
		if (!token || !projectId) return null;
		const wsId = pendingWorkspaceId;
		const conv = await api.post<Conversation>(
			'/api/v1/chat/conversations',
			{
				title: firstMessage.slice(0, 60),
				model_name: selectedModel || null,
				workspace_id: wsId
			},
			token,
			projectId
		);
		pendingWorkspaceId = null;
		activeConvId = conv.id;
		conversations = [conv, ...conversations];
		return conv.id;
	}

	// --- Durable run journal ---
	function endStream() {
		streaming = false;
		toolActivity = null;
		agentActivity = null;
		stream = null;
		currentRun = null;
	}

	function completedToolText(parts: { type: string; text?: string }[]): string {
		return parts
			.map((part) => (part.type === 'text' && typeof part.text === 'string' ? part.text : `[${part.type}]`))
			.join('\n');
	}

	async function followRun(
		descriptor: ChatRunDescriptor,
		draft: DisplayMessage,
		onDone: (metrics: StreamMetrics | null) => Promise<void> | void,
		generation: number
	) {
		let firstTokenMs: number | null = null;
		let charCount = 0;
		const controller = new AbortController();
		if (!streamAttachment.attach(controller, generation)) return;
		const reveal = createChatRevealBuffer({
			reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
		});
		let revealFrame: number | null = null;
		let revealCompletion: (() => void) | null = null;

		function renderReveal() {
			if (revealFrame !== null) revealFrames.delete(revealFrame);
			revealFrame = null;
			if (destroyed || generation !== streamGeneration) {
				revealCompletion?.();
				revealCompletion = null;
				return;
			}
			const next = reveal.frame();
			draft.content = next.text;
			if (next.pending) scheduleReveal();
			else {
				revealCompletion?.();
				revealCompletion = null;
			}
		}
		function scheduleReveal() {
			if (revealFrame !== null || destroyed || generation !== streamGeneration) return;
			revealFrame = requestAnimationFrame(renderReveal);
			revealFrames.add(revealFrame);
		}
		function drainReveal() {
			if (revealFrame !== null) {
				cancelAnimationFrame(revealFrame);
				revealFrames.delete(revealFrame);
			}
			revealFrame = null;
			draft.content = reveal.drain();
			revealCompletion?.();
			revealCompletion = null;
		}
		function finishReveal() {
			reveal.finish();
			if (destroyed || generation !== streamGeneration || controller.signal.aborted) {
				return Promise.resolve();
			}
			return new Promise<void>((resolve) => {
				const complete = () => {
					controller.signal.removeEventListener('abort', complete);
					if (revealCompletion === complete) revealCompletion = null;
					resolve();
				};
				revealCompletion = complete;
				controller.signal.addEventListener('abort', complete, { once: true });
				scheduleReveal();
			});
		}

		try {
			let runState = createRunViewState(descriptor.run_id);
			for await (const evt of followChatRun(descriptor, { token, projectId, signal: controller.signal })) {
				if (destroyed || generation !== streamGeneration) return;
				runState = reduceRunEvent(runState, evt);
				if (evt.type === 'run.stage.changed') {
					agentActivity = activityForRunStage(evt.payload.stage, evt.created_at, evt.payload.tool_name);
				}
				if (evt.type === 'part.delta' || evt.type === 'part.completed') {
					const authoritativeText = runState.parts
						.filter((part) => part.type === 'text')
						.map((part) => part.text)
						.join('');
					draft.reasoning = runState.parts
						.filter((part) => part.type === 'reasoning')
						.map((part) => part.text)
						.join('');
					draft.citations = runState.parts.filter((part) => part.type === 'citation');
					if (evt.type === 'part.delta' && evt.payload.part_type === 'text') {
						const receivedAtMs = performance.now();
						reveal.append(evt.payload.delta, Date.parse(evt.created_at), receivedAtMs);
						scheduleReveal();
						toolActivity = null;
						if (firstTokenMs === null) firstTokenMs = performance.now();
						charCount += evt.payload.delta.length;
						draft.metrics = computeMetrics(
							estimateTokens(charCount),
							firstTokenMs,
							performance.now(),
							true
						);
					} else if (evt.type === 'part.completed' && evt.payload.part.type === 'text') {
						reveal.reconcile(authoritativeText);
						scheduleReveal();
					}
				} else if (evt.type === 'tool.call.started' || evt.type === 'tool.call.completed') {
					draft.toolItems = Object.values(runState.tools).map((tool) => ({
						id: tool.callId,
						name: tool.name,
						args: JSON.stringify(tool.arguments),
						result: completedToolText(tool.content),
						running: tool.status === 'running'
					}));
					toolActivity = evt.type === 'tool.call.started' ? evt.payload.name : null;
				} else if (evt.type === 'usage.updated') {
					draft.metrics = computeMetrics(
						evt.payload.completion_tokens,
						firstTokenMs,
						performance.now(),
						false
					);
				} else if (evt.type === 'run.completed') {
					await finishReveal();
					if (generation !== streamGeneration || destroyed) return;
					draft.streaming = false;
					await onDone(draft.metrics ?? null);
					if (generation !== streamGeneration || destroyed) return;
					endStream();
					return;
				} else if (evt.type === 'run.failed' || evt.type === 'run.canceled') {
					drainReveal();
					error = evt.payload.safe_message;
					endStream();
					return;
				}
			}
		} catch (caught) {
			if (destroyed || controller.signal.aborted || generation !== streamGeneration) return;
			drainReveal();
			error = caught instanceof Error ? caught.message : '채팅 실행 중 오류가 발생했습니다';
			endStream();
		} finally {
			streamAttachment.release(controller);
			revealCompletion?.();
			revealCompletion = null;
			if (revealFrame !== null) {
				cancelAnimationFrame(revealFrame);
				revealFrames.delete(revealFrame);
			}
		}
	}

	async function runStream(
		path: string,
		body: unknown,
		draft: DisplayMessage,
		onDone: (metrics: StreamMetrics | null) => Promise<void> | void,
		onStarted?: (descriptor: ChatRunDescriptor) => void
	) {
		const generation = streamGeneration;
		try {
			const descriptor = await createChatRun(path, body, { token, projectId });
			if (destroyed || generation !== streamGeneration) return;
			currentRun = descriptor;
			onStarted?.(descriptor);
			await followRun(descriptor, draft, onDone, generation);
		} catch (caught) {
			if (destroyed || generation !== streamGeneration) return;
			error = caught instanceof Error ? caught.message : '채팅 실행 중 오류가 발생했습니다';
			endStream();
		}
	}

	async function resumeActiveRun(conversationId: string) {
		if (!token || !projectId || tempMode || currentRun) return;
		const generation = streamGeneration;
		try {
			const payload = await api.get<unknown[]>(
				`/api/v1/chat/conversations/${conversationId}/runs?active=true`,
				token,
				projectId
			);
			const descriptor = payload.map(parseChatRunDescriptor)[0];
			if (!descriptor) {
				if (
					activeConvId === conversationId &&
					!tempMode &&
					generation === streamGeneration &&
					!destroyed
				) {
					setConversationRun(conversationId, false);
					await loadMessages(conversationId, selectionGeneration);
				}
				return;
			}
			if (
				activeConvId !== conversationId ||
				currentRun ||
				destroyed ||
				generation !== streamGeneration
			)
				return;

			const draft = newAssistantDraft(activeConv?.model_name ?? selectedModel);
			streaming = true;
			currentRun = descriptor;
			setConversationRun(conversationId, true);
			stream = { base: activePath, assistant: draft, conversationId, temp: false };
			void followRun(
				descriptor,
				draft,
				async (metrics) => {
					setConversationRun(conversationId, false);
					if (activeConvId === conversationId && !tempMode) {
						const selection = selectionGeneration;
						if (await loadMessages(conversationId, selection) && metrics && activeLeafId) {
							metricsById.set(activeLeafId, metrics);
						}
					}
					void loadConversations();
					void loadUsage();
				},
				generation
			);
		} catch {
			// A completed/deleted run or a transient list failure must not block opening the conversation.
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
		if (attachments.some((attachment) => attachment.status === 'uploading')) {
			error = '첨부 업로드가 완료된 뒤 전송할 수 있습니다.';
			return;
		}
		const inputParts: UserInputPart[] = [{ type: 'text', text }, ...toInputParts(attachments)];
		attachments = [];

		if (tempMode) return sendTemp(text, inputParts);

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
		stream = { base: [...activePath, userMsg], assistant: newAssistantDraft(selectedModel), conversationId: convId, temp: false };
		// $state 프록시를 경유해 mutate 해야 반응성이 발생한다(raw draft 직접 쓰기는 트랩 우회).
		const live = stream.assistant;

		await runStream(
			`/api/v1/chat/conversations/${convId}/completions`,
			{
				parts: inputParts,
				model_id: selectedModel,
				features: selectedFeatureOptions(),
				reasoning_effort: effort,
				agent_id: activeAgent?.id,
				skill_ids: selectedSkillIds,
			},
			live,
			async (metrics) => {
				setConversationRun(convId!, false);
				if (activeConvId === convId && !tempMode) {
					const selection = selectionGeneration;
					if (await loadMessages(convId!, selection) && metrics && activeLeafId) {
						metricsById.set(activeLeafId, metrics);
					}
				}
				void loadConversations();
				void loadUsage();
			},
			() => setConversationRun(convId!, true)
		);
	}

	async function sendTemp(
		text: string,
		inputParts: UserInputPart[]
	) {
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
		stream = { base: history, assistant: newAssistantDraft(selectedModel), conversationId: null, temp: true };
		const live = stream.assistant; // 프록시 경유(반응성)

		await runStream(
			'/api/v1/chat/temp-completions',
			{
				parts: inputParts,
				model_id: selectedModel,
				features: selectedFeatureOptions(),
				temp_thread_id: tempThreadId,
				reasoning_effort: effort,
				skill_ids: selectedSkillIds,
			},
			live,
			(metrics) => {
				// 임시 채팅은 저장되지 않으므로 완료된 답변을 로컬 배열에 확정(계측값 포함)
				tempMessages = [...history, { ...live, streaming: false, metrics }];
				void loadUsage();
			},
			(descriptor) => rememberTempThread(descriptor.temp_thread_id)
		);
	}

	// --- 재생성 ---
	async function regenerate(messageId: string, modelName: string) {
		if (streaming || tempMode || !activeConvId || !token || !projectId) return;
		const conversationId = activeConvId;
		error = null;
		const idx = activePath.findIndex((m) => m.id === messageId);
		if (idx === -1) return;
		streaming = true;
		stream = { base: activePath.slice(0, idx), assistant: newAssistantDraft(modelName || selectedModel), conversationId, temp: false };
		const live = stream.assistant; // 프록시 경유(반응성)

		await runStream(
			`/api/v1/chat/conversations/${conversationId}/messages/${messageId}/regenerate`,
			{
				model_id: modelName || selectedModel,
				features: selectedFeatureOptions(),
				reasoning_effort: effort,
				skill_ids: selectedSkillIds,
			},
			live,
			async (metrics) => {
				setConversationRun(conversationId, false);
				if (activeConvId === conversationId && !tempMode) {
					const selection = selectionGeneration;
					if (await loadMessages(conversationId, selection) && metrics && activeLeafId) {
						metricsById.set(activeLeafId, metrics);
					}
				}
				void loadConversations();
				void loadUsage();
			},
			() => setConversationRun(conversationId, true)
		);
	}

	// --- 버전 전환 ---
	async function switchVersion(messageId: string, direction: -1 | 1) {
		if (streaming || tempMode || !activeConvId || !token || !projectId) return;
		const msg = allMessages.find((m) => m.id === messageId);
		if (!msg) return;
		const targetLeaf = siblingLeafInDirection(treeNodes, msg, direction);
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

	async function stop() {
		if (!currentRun || !token || !projectId) return;
		try {
			await cancelChatRun(currentRun, { token, projectId });
		} catch (caught) {
			error = caught instanceof Error ? caught.message : '실행 중지 요청에 실패했습니다';
		}
	}
	function copy(text: string) {
		void navigator.clipboard?.writeText(text);
	}

	// 최초 1회: 모바일이면 사이드바를 접은 상태로 시작(본문 우선 표시)
	$effect(() => {
		untrack(() => {
			try {
				tempThreadId = sessionStorage.getItem(_TEMP_THREAD_KEY);
			} catch {
				// Browser storage is optional; no temporary content is persisted here.
			}
			if (isMobile()) sidebarOpen = false;
		});
	});

	// 최초 로드 — 초기 동시 쿼리 폭주가 chat DB 커넥션 풀(size 5)을 고갈시켜
	// 경합/플래핑(503)을 유발하므로 2파도로 나눈다: 핵심(첫 화면) 먼저 동시, 보조는 그 뒤 순차.
	$effect(() => {
		void [token, projectId];
		untrack(() => {
			void (async () => {
				await Promise.allSettled([loadConversations(), loadModels(), loadUsage()]);
				// 보조: 에이전트·프로젝트·확장(tool/MCP/skill)은 초기 버스트에서 제외해 풀 경합 완화.
				await loadAgents();
				await loadWorkspaces();
				await loadToolsAndMcp();
			})();
		});
	});
</script>

<div class="chat-shell" class:sidebar-closed={!sidebarOpen}>
	<ChatSidebar
		{conversations}
		{workspaces}
		{activeConvId}
		{tempMode}
		open={sidebarOpen}
		{usage}
		busy={streaming}
		{runningConversationIds}
		onSelect={selectConversation}
		onNew={newConversation}
		onDelete={deleteConversation}
		onAssign={assignWorkspace}
		onAgents={() => (agentManagerOpen = true)}
		onWorkspaces={openProjects}
		onOpenWorkspace={openProjectWorkspace}
		onToggle={toggleSidebar}
		onNewInWorkspace={newInProject}
		onDeleteWorkspace={deleteWorkspace}
		onSearch={searchConversations}
		onSettings={() => (settingsOpen = true)}
	/>

	<nav class="sidebar-rail" aria-label="채팅 탐색">
		<button
			type="button"
			class="rail-action rail-open"
			onclick={toggleSidebar}
			title="사이드바 열기"
			aria-label="사이드바 열기"
		>
			<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3.5" y="4" width="17" height="16" rx="2.5" /><path d="M10 4v16" /></svg>
		</button>
		<span class="rail-divider" aria-hidden="true"></span>
		<button type="button" class="rail-action" onclick={newConversation} title="새 채팅" aria-label="새 채팅">
			<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	</nav>

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
				initialMode={projectsInitialMode}
				initialWorkspaceId={projectsInitialWorkspaceId}
				{conversations}
				{workspaces}
				onCreate={createWorkspace}
				onUpdate={updateWorkspace}
				onDelete={deleteWorkspace}
				onAssign={assignWorkspace}
				onOpenConversation={selectConversation}
				onNewInProject={newInProject}
				onNavigate={navigateProjectRoute}
			/>
		{:else}
			<header class="head">
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
						<span class="model-btn-caps"><ModelCapabilityBadges caps={selectedModelObj?.capabilities} size="xs" iconsOnly /></span>
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
				{#if tempMode || !tempToggleLocked}
					<button
						type="button"
						class="temp-btn"
						class:active={tempMode}
						disabled={tempToggleLocked}
						onclick={toggleTempChat}
						title={tempToggleLocked ? '시작된 채팅에서는 임시 모드를 변경할 수 없습니다' : '저장되지 않는 임시 채팅'}
						aria-pressed={tempMode}
					>
						<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-dasharray="2.5 1.5" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-8 7.48 7.4 7.4 0 0 1-3.16-0.9L4 20l1.42-4.1A7.5 7.5 0 1 1 20 11.5z" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/if}
			</div>
			{#if tempMode}
				<p class="temp-notice" role="status">
					<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 8v4l2.5 2.5M12 3a9 9 0 1 0 9 9" stroke-linecap="round" stroke-linejoin="round" /></svg>
					이 대화는 저장되지 않으며 30일 후 삭제됩니다.
				</p>
			{/if}
		</header>

		<div class="chat-workspace" class:empty-workspace={isEmpty} class:temp-mode={tempMode}>
		<ChatWindow
			activePath={displayPath}
			treeNodes={treeSource}
			{metricsById}
			{models}
			busy={streaming}
			loading={treeLoading}
			{modelLocked}
			{toolActivity}
			{agentActivity}
			{error}
			empty={isEmpty}
			conversationKey={activeConvId ?? (tempMode ? tempThreadId ?? 'temporary' : '')}
			hasOlder={historyHasMore}
			loadingOlder={historyLoading}
			onLoadOlder={loadOlderMessages}
			onCopy={copy}
			onRegenerate={regenerate}
			onFork={fork}
			onSwitchVersion={switchVersion}
		/>


			<div class="composer-anchor" bind:this={composerAnchor}>
				<ChatInput
					bind:value={input}
					bind:effort
					bind:attachments
					bind:selectedToolIds
					bind:selectedMcpIds
					bind:selectedSkillIds
					{availableTools}
					{availableMcp}
					{availableSkills}
					{token}
					{projectId}
					modelCaps={selectedModelObj?.capabilities}
					{streaming}
					onSend={send}
					onStop={stop}
				>
					{#if isEmpty && !tempMode}
						<div class="composer-meta">
							<ConversationWorkspacePicker
								{workspaces}
								currentWorkspaceId={currentWorkspaceId}
								disabled={streaming}
								onChange={changeConversationWorkspace}
								onCreateProject={createProject}
							/>
						</div>
					{:else if isEmpty}
						<div class="composer-meta composer-meta-reserve" aria-hidden="true"></div>
					{/if}
				</ChatInput>
			</div>
		</div>
		{/if}
	</section>
</div>

<CreateProjectDialog
	open={createProjectDialogOpen}
	onClose={() => (createProjectDialogOpen = false)}
	onCreate={createProjectFromDialog}
/>

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
	.sidebar-rail {
		display: none;
	}
	.rail-action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.35rem;
		height: 2.35rem;
		border: 1px solid transparent;
		border-radius: 0.6rem;
		background: transparent;
		color: var(--color-ink-2);
		cursor: pointer;
		transition: background 0.12s, border-color 0.12s, color 0.12s;
	}
	.rail-action:hover,
	.rail-action:focus-visible {
		border-color: var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-0);
	}
	.rail-open {
		position: relative;
	}
	.rail-open:hover::after,
	.rail-open:focus-visible::after {
		content: '사이드바 열기';
		position: absolute;
		z-index: 20;
		top: 50%;
		left: calc(100% + 0.6rem);
		width: max-content;
		padding: 0.42rem 0.6rem;
		border-radius: 0.45rem;
		background: var(--color-ink-0);
		color: var(--color-surface-base);
		font-size: 0.75rem;
		font-weight: 600;
		transform: translateY(-50%);
		pointer-events: none;
	}
	.rail-divider {
		width: 1.35rem;
		height: 1px;
		margin: 0.15rem 0;
		background: var(--color-line);
	}
	@media (max-width: 768px) {
		.chat-shell.sidebar-closed .sidebar-rail {
			display: flex;
			position: fixed;
			z-index: 31;
			top: 0.65rem;
			left: 0.65rem;
			flex-direction: column;
			align-items: center;
			padding: 0.2rem;
			border: 1px solid var(--color-line);
			border-radius: 0.65rem;
			background: var(--color-surface-raised);
			box-shadow: 0 8px 24px color-mix(in oklab, var(--color-ink-0) 14%, transparent);
		}
		.chat-shell.sidebar-closed .rail-divider,
		.chat-shell.sidebar-closed .rail-action:not(.rail-open) {
			display: none;
		}
	}
	@media (min-width: 769px) {
		.chat-shell.sidebar-closed .sidebar-rail {
			display: flex;
			flex: 0 0 3.25rem;
			flex-direction: column;
			align-items: center;
			gap: 0.35rem;
			padding-top: 0.7rem;
			border-right: 1px solid var(--color-line);
			background: var(--color-surface-sunken);
		}
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
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 0.55rem 1rem;
		box-sizing: border-box;
		block-size: 3.75rem;
		padding: 0.7rem 1rem;
		border-bottom: 1px solid var(--color-line);
		background: var(--color-surface-base);
	}
	.head-center {
		grid-column: 1;
		grid-row: 1;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.2rem;
		min-width: 0;
	}
	.head-controls {
		display: flex;
		align-items: center;
		flex-wrap: nowrap;
		gap: 0.5rem;
		inline-size: 100%;
		min-width: 0;
	}
	.model-lock-hint {
		font-size: 0.66rem;
		color: var(--color-ink-3);
	}
	.chat-workspace {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
	}
	.chat-workspace:not(.empty-workspace) :global(.window) {
		width: 100%;
		margin-inline: 0;
	}
	.chat-workspace :global(.composer) {
		width: min(100%, 64rem);
		margin-inline: auto;
	}
	.chat-workspace.temp-mode {
		background: var(--color-surface-sunken);
	}
	.chat-workspace.empty-workspace {
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}
	.chat-workspace.empty-workspace :global(.window),
	.chat-workspace.empty-workspace .composer-anchor {
		width: min(100%, 42rem);
		flex: 0 0 auto;
	}
	.chat-workspace.empty-workspace :global(.window) {
		margin-bottom: 0.25rem;
	}
	.chat-workspace.empty-workspace :global(.window .scroll) {
		flex: none;
		padding: 0;
		overflow: visible;
	}
	.chat-workspace.empty-workspace :global(.window .welcome) {
		height: auto;
		padding: 0 0 1.25rem;
	}
	.composer-meta {
		display: flex;
		align-items: center;
		box-sizing: border-box;
		width: 100%;
		min-height: 3.15rem;
		padding: 0.52rem 1rem 0.6rem;
		border: none;
		border-radius: 0 0 1rem 1rem;
		background: var(--color-surface-sunken);
		pointer-events: none;
	}
	.composer-meta-reserve {
		visibility: hidden;
	}
	.composer-meta :global(.wsp) {
		width: auto;
		pointer-events: auto;
	}
	.composer-meta :global(.wsp .trigger) {
		width: auto;
		justify-content: flex-start;
	}
	.composer-meta :global(.wsp .chev) {
		margin-left: 0;
	}
	.model-btn {
		display: inline-flex;
		flex: 1 1 12rem;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
		max-width: 20rem;
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
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.temp-btn {
		display: inline-flex;
		flex: 0 0 2.35rem;
		align-items: center;
		justify-content: center;
		width: 2.35rem;
		height: 2.35rem;
		padding: 0;
		border: 1px dashed transparent;
		border-radius: 50%;
		background: transparent;
		color: var(--color-ink-2);
		cursor: pointer;
		transition: background 0.15s, color 0.15s, border-color 0.15s;
	}
	.temp-btn:hover:not(:disabled) {
		color: var(--color-ink-0);
		border-color: var(--color-line);
		background: var(--color-surface-raised);
	}
	.temp-btn.active {
		background: var(--color-surface-sunken);
		color: var(--color-accent);
		border-color: var(--color-line-2);
	}
	.temp-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.temp-notice {
		grid-column: 1 / -1;
		grid-row: 2;
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0;
		color: var(--color-ink-2);
		font-size: 0.72rem;
	}
	.head-right {
		grid-column: 2;
		grid-row: 1;
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
	.model-btn-caps {
		display: inline-flex;
		flex: 0 0 auto;
	}
	.model-btn-caps :global(.badges) {
		flex-wrap: nowrap;
	}
	.head-controls :global(.agent-picker) {
		flex: 0 0 auto;
	}
	@media (max-width: 900px) {
		.head-controls :global(.agent-label) {
			display: none;
		}
		.head-controls :global(.agent-picker .trigger) {
			padding-inline: 0.5rem;
		}
	}
	/* 모바일: 헤더 과밀 완화 — 제목·헤더 배지 숨기고 컨트롤 축소, 줄바꿈 방지 */
	@media (max-width: 640px) {
		.head {
			gap: 0.4rem;
			padding: 0.55rem 0.6rem;
		}
		.head-controls {
			gap: 0.3rem;
		}
		.model-btn {
			max-width: 11rem;
			padding: 0.4rem 0.55rem;
		}
		/* 능력 배지는 입력창 하단(Vision/Think/Tools)에 이미 표시 — 헤더에선 숨김 */
		.model-btn-caps {
			display: none;
		}
	}
</style>
