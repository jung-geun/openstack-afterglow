import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '$lib/stores/auth';
import { parseChatRunEvent } from '$lib/api/chatContracts';
import ChatPanel from '../ChatPanel.svelte';

const mocks = vi.hoisted(() => ({
	get: vi.fn(),
	post: vi.fn(),
	createRun: vi.fn(),
	followRun: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	api: {
		get: mocks.get,
		post: mocks.post,
		patch: vi.fn(),
		put: vi.fn(),
		delete: vi.fn()
	},
	ApiError: class ApiError extends Error {}
}));

vi.mock('$lib/api/chatStream', () => ({
	createChatRun: mocks.createRun,
	followChatRun: mocks.followRun,
	cancelChatRun: vi.fn(),
	parseChatRunDescriptor: (value: unknown) => value
}));

let nextAnimationFrame = 0;
const animationFrames = new Map<number, FrameRequestCallback>();

function flushAnimationFrames() {
	const queued = [...animationFrames.values()];
	animationFrames.clear();
	for (const callback of queued) callback(performance.now());
}

const at = '2026-07-26T00:00:00Z';

function event(seq: number, type: string, payload: object) {
	return parseChatRunEvent({
		event_id: `run-1:${seq}`,
		run_id: 'run-1',
		seq,
		type,
		created_at: at,
		payload
	});
}

beforeEach(() => {
	vi.clearAllMocks();
	auth.set({
		token: 'token',
		refreshToken: null,
		accessExpiresAt: null,
		userId: 'user-1',
		username: 'tester',
		projectId: 'project-1',
		projectName: 'Project',
		availableProjects: [],
		roles: [],
		isSystemAdmin: false,
		federated: false
	});
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query.includes('prefers-reduced-motion'),
		media: query,
		onchange: null,
		addEventListener: () => {},
		removeEventListener: () => {},
		addListener: () => {},
		removeListener: () => {},
		dispatchEvent: () => false
	}));
	animationFrames.clear();
	nextAnimationFrame = 0;
	vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
		const frame = ++nextAnimationFrame;
		animationFrames.set(frame, callback);
		return frame;
	});
	vi.stubGlobal('cancelAnimationFrame', (frame: number) => animationFrames.delete(frame));
	mocks.get.mockImplementation(async (path: string) => {
		if (path === '/api/v1/chat/models') {
			return [{ id: 1, model_name: 'model-1', display_name: 'Model 1' }];
		}
		if (path === '/api/v1/chat/runs?active=true') return [];
		if (path === '/api/v1/chat/conversations') return [];
		if (path === '/api/v1/chat/usage') return {};
		return [];
	});
	mocks.createRun.mockResolvedValue({
		run_id: 'run-1',
		conversation_id: null,
		temp_thread_id: 'temp-1',
		status: 'running',
		events_url: '/events',
		cancel_url: '/cancel'
	});
	mocks.followRun.mockImplementation(async function* () {});
	mocks.post.mockResolvedValue({});
});

describe('ChatPanel', () => {
	it('renders an empty chat without a derived-state initialization error', () => {
		render(ChatPanel);

		expect(screen.getByRole('heading', { name: '무엇을 도와드릴까요?' })).toBeTruthy();
	});


	it('inserts a Lumen starter into the composer without directly starting a run', async () => {
		render(ChatPanel);

		await fireEvent.click(screen.getByRole('button', { name: '프로젝트 현황' }));

		expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe(
			'현재 프로젝트의 컴퓨팅, 스토리지, 네트워크 리소스를 읽기 전용으로 요약해 주세요.'
		);
		expect(mocks.createRun).not.toHaveBeenCalled();
	});

	it('keeps a pre-persistence send failure visible and retries with the same request key', async () => {
		mocks.post.mockImplementation(async (path: string) => {
			if (path === '/api/v1/chat/conversations') {
				return {
					id: 'conversation-1',
					title: '재시도',
					model_name: 'model-1',
					workspace_id: null,
					updated_at: at
				};
			}
			return {};
		});
		const retry = Promise.withResolvers<object>();
		mocks.createRun
			.mockRejectedValueOnce(new Error('일시적으로 전송하지 못했습니다'))
			.mockImplementationOnce(() => retry.promise);

		render(ChatPanel);
		await fireEvent.input(screen.getByRole('textbox'), { target: { value: '실패 후 재전송' } });
		await fireEvent.click(screen.getByRole('button', { name: '전송' }));

		await screen.findByText('응답 생성에 실패했습니다');
		expect(screen.getByText('실패 후 재전송')).toBeTruthy();
		const retryButton = screen.getByRole('button', { name: '다시 전송' });
		await fireEvent.click(retryButton);
		await fireEvent.click(retryButton);

		await waitFor(() => expect(mocks.createRun).toHaveBeenCalledTimes(2));
		const firstOptions = mocks.createRun.mock.calls[0][2];
		const retryOptions = mocks.createRun.mock.calls[1][2];
		expect(retryOptions.idempotencyKey).toBe(firstOptions.idempotencyKey);
		retry.resolve({
			run_id: 'run-retry',
			conversation_id: 'conversation-1',
			temp_thread_id: null,
			status: 'queued',
			events_url: '/events',
			cancel_url: '/cancel'
		});
	});
	it('keeps a failed conversation creation attempt visible with retry button and retries conversation creation on click', async () => {
		let attempts = 0;
		mocks.post.mockImplementation(async (path: string) => {
			if (path === '/api/v1/chat/conversations') {
				attempts += 1;
				if (attempts === 1) {
					throw new Error('대화 생성 실패');
				}
				return {
					id: 'conversation-created',
					title: '첫 대화 생성 실패 후 복구',
					model_name: 'model-1',
					workspace_id: null,
					updated_at: at
				};
			}
			return {};
		});

		render(ChatPanel);
		await fireEvent.input(screen.getByRole('textbox'), { target: { value: '첫 생성 실패 메시지' } });
		await fireEvent.click(screen.getByRole('button', { name: '전송' }));

		await screen.findByText('응답 생성에 실패했습니다');
		expect(screen.getByText('첫 생성 실패 메시지')).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: '다시 전송' }));

		await waitFor(() => expect(attempts).toBe(2));
		await waitFor(() => expect(mocks.createRun).toHaveBeenCalledTimes(1));
		expect(mocks.createRun.mock.calls[0][0]).toBe('/api/v1/chat/conversations/conversation-created/completions');
	});

	it('keeps the live bubble on the current message when a prior completion arrives late', async () => {
		mocks.followRun.mockImplementation(async function* () {
			yield event(1, 'message.created', { message_id: 'assistant-1', role: 'assistant', parent_id: null });
			yield event(2, 'part.delta', {
				message_id: 'assistant-1',
				part_index: 1,
				part_type: 'reasoning',
				delta: '이전 추론'
			});
			yield event(3, 'part.delta', {
				message_id: 'assistant-1',
				part_index: 0,
				part_type: 'text',
				delta: '이전 본문'
			});
			yield event(4, 'message.created', { message_id: 'assistant-2', role: 'assistant', parent_id: null });
			yield event(5, 'part.completed', {
				message_id: 'assistant-1',
				part_index: 1,
				part: { type: 'reasoning', text: '이전 추론', visibility: 'user' }
			});
			yield event(6, 'part.completed', {
				message_id: 'assistant-1',
				part_index: 0,
				part: { type: 'text', text: '이전 본문' }
			});
			yield event(7, 'part.delta', {
				message_id: 'assistant-2',
				part_index: 0,
				part_type: 'text',
				delta: '현재 본문'
			});
			yield event(8, 'part.completed', {
				message_id: 'assistant-2',
				part_index: 0,
				part: { type: 'text', text: '현재 본문' }
			});
			yield event(9, 'run.completed', { status: 'completed', message_id: 'assistant-2' });
		});

		render(ChatPanel);
		await waitFor(() =>
			expect(mocks.get).toHaveBeenCalledWith('/api/v1/chat/models', 'token', 'project-1')
		);
		await fireEvent.click(screen.getByTitle('저장되지 않는 임시 채팅'));
		await fireEvent.input(
			screen.getByRole('textbox'),
			{ target: { value: '테스트' } }
		);
		await waitFor(() => expect(screen.getByRole('button', { name: '전송' }).hasAttribute('disabled')).toBe(false));
		await fireEvent.click(screen.getByRole('button', { name: '전송' }));
		await waitFor(() => expect(mocks.createRun).toHaveBeenCalledTimes(1));
		await waitFor(() => {
			flushAnimationFrames();
			expect(screen.getByText('현재 본문')).toBeTruthy();
		});
		expect(screen.queryByText('이전 본문')).toBeNull();

		await fireEvent.click(screen.getByLabelText('작업 내역 열기'));
		await fireEvent.click(screen.getByRole('button', { name: '추론 과정' }));
		expect(screen.getByText('이전 추론')).toBeTruthy();
	});

	it('renders an approval preview and sends an explicit project-scoped decision', async () => {
		mocks.followRun.mockImplementation(async function* () {
			yield event(1, 'tool.approval_required', {
				call_id: 'call-1',
				name: 'afterglow_vm_delete',
				source: 'managed',
				effect: 'external_mutation',
				destination: null,
				redacted_arguments: { server_id: '[REDACTED]' },
				preview: [{ type: 'text', text: 'Delete: server-1 (current state: ACTIVE)' }],
				expected_state_revision: null,
				writer_fence: null,
				expires_at: '2026-07-27T12:00:00Z'
			});
		});

		render(ChatPanel);
		await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('/api/v1/chat/models', 'token', 'project-1'));
		await fireEvent.click(screen.getByTitle('저장되지 않는 임시 채팅'));
		await fireEvent.input(screen.getByRole('textbox'), { target: { value: 'VM을 삭제해줘' } });
		await fireEvent.click(screen.getByRole('button', { name: '전송' }));

		await screen.findByText('Delete: server-1 (current state: ACTIVE)');
		await fireEvent.click(screen.getByRole('button', { name: '승인' }));

		expect(mocks.post).toHaveBeenCalledWith(
			'/api/v1/chat/runs/run-1/approvals/call-1',
			{ decision: 'approve' },
			'token',
			'project-1'
		);
	});
});
