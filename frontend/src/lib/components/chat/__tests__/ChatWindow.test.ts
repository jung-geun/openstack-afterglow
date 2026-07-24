import { fireEvent, render } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import ChatWindow from '../ChatWindow.svelte';

const callbacks = {
	onCopy: () => {},
	onRegenerate: () => {},
	onFork: () => {},
	onSwitchVersion: () => {}
};

describe('ChatWindow', () => {
	it('shows the durable agent stage and elapsed time', () => {
		const { getByRole } = render(ChatWindow, {
			activePath: [],
			allMessages: [],
			models: [],
			agentActivity: {
				label: 'web_search 도구를 실행 중입니다',
				startedAt: new Date(Date.now() - 2_000).toISOString()
			},
			...callbacks
		});

		const status = getByRole('status');
		expect(status.textContent).toContain('web_search 도구를 실행 중입니다');
		expect(status.textContent).toContain('초');
	});

	it('renders a non-empty conversation without an undefined component error', () => {
		const { getByText } = render(ChatWindow, {
			activePath: [
				{
					id: 'message-1',
					conversation_id: 'conversation-1',
					role: 'user',
					parent_id: null,
					content: '확인할 메시지',
					created_at: '2026-07-23T00:00:00Z'
				}
			],
			models: [],
			...callbacks
		});

		expect(getByText('확인할 메시지')).toBeTruthy();
	});

	it('shows an explicit follow control after the reader scrolls away from streaming output', async () => {
		const { container, getByRole } = render(ChatWindow, {
			activePath: [],
			allMessages: [],
			models: [],
			busy: true,
			...callbacks
		});
		await tick();
		const scroll = container.querySelector('.scroll') as HTMLDivElement;
		Object.defineProperties(scroll, {
			scrollHeight: { configurable: true, value: 1_000 },
			clientHeight: { configurable: true, value: 100 },
			scrollTop: { configurable: true, value: 0, writable: true }
		});

		await fireEvent.scroll(scroll);
		await tick();

		expect(getByRole('button', { name: '새 응답 따라가기' })).toBeTruthy();
	});

	it('preserves scroll offset while its older-history callback prepends messages', async () => {
		let scroll: HTMLDivElement;
		const onLoadOlder = vi.fn(async () => {
			Object.defineProperty(scroll, 'scrollHeight', { configurable: true, value: 1_200 });
		});
		const { container } = render(ChatWindow, {
			activePath: [],
			allMessages: [],
			models: [],
			hasOlder: true,
			onLoadOlder,
			...callbacks
		});
		scroll = container.querySelector('.scroll') as HTMLDivElement;
		Object.defineProperties(scroll, {
			scrollHeight: { configurable: true, value: 1_000 },
			clientHeight: { configurable: true, value: 100 },
			scrollTop: { configurable: true, value: 0, writable: true }
		});

		await fireEvent.scroll(scroll);

		expect(onLoadOlder).toHaveBeenCalledOnce();
		expect(scroll.scrollTop).toBe(200);
	});
});
