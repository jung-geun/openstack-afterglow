import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '$lib/stores/auth';

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('$lib/api/client', () => ({
	api: { get: mocks.get, post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
	ApiError: class ApiError extends Error {}
}));

import ChatSettingsOverlay from '../ChatSettingsOverlay.svelte';

describe('ChatSettingsOverlay', () => {
	beforeEach(() => {
		mocks.get.mockReset();
		auth.set({
			token: 'browser-token', refreshToken: null, accessExpiresAt: null,
			userId: 'user-1', username: 'tester', projectId: 'project-1', projectName: 'Project',
			availableProjects: [], roles: [], isSystemAdmin: false, federated: false
		});
		mocks.get.mockImplementation((path: string) => {
			if (path.endsWith('/memories/document')) {
				return Promise.resolve({
					filename: 'memory.md',
					content_type: 'text/markdown',
					content: '# Memory\n\n## Preferences\n\n- Prefers concise answers\n'
				});
			}
			if (path.endsWith('/memories')) return Promise.resolve([]);
			return Promise.resolve([]);
		});
	});

	it('opens on usage and leaves theme controls to the global header', () => {
		render(ChatSettingsOverlay, { open: true, onClose: () => {}, usage: null });

		expect(screen.getByRole('button', { name: '사용량' })).toBeTruthy();
		expect(screen.getByRole('heading', { name: '이번 달 사용량' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: '라이트' })).toBeNull();
		expect(screen.queryByRole('button', { name: '다크' })).toBeNull();
		expect(screen.queryByRole('button', { name: '시스템' })).toBeNull();
	});

	it('shows the automatically maintained memory.md and copies its plaintext content', async () => {
		const writeText = vi.fn().mockResolvedValue(undefined);
		Object.defineProperty(navigator, 'clipboard', {
			configurable: true,
			value: { writeText }
		});
		render(ChatSettingsOverlay, {
			open: true,
			onClose: () => {},
			usage: null,
			initialSection: 'memory'
		});

		const document = await screen.findByLabelText('memory.md 내용');
		expect(document.textContent).toContain('# Memory');
		expect(document.textContent).toContain('Prefers concise answers');
		expect(mocks.get).toHaveBeenCalledWith(
			'/api/v1/chat/memories/document',
			'browser-token',
			'project-1'
		);

		await fireEvent.click(screen.getByRole('button', { name: '복사' }));
		await waitFor(() =>
			expect(writeText).toHaveBeenCalledWith(expect.stringContaining('Prefers concise answers'))
		);
	});
});
