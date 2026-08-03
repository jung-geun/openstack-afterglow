import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import ConversationWorkspacePicker from '../ConversationWorkspacePicker.svelte';

describe('ConversationWorkspacePicker', () => {
	it('closes its project list when the user clicks outside', async () => {
		render(ConversationWorkspacePicker, {
			workspaces: [{ id: 1, name: 'dms cloud', description: null, instructions: null }],
			currentWorkspaceId: null,
			onChange: vi.fn(),
			onCreateProject: vi.fn()
		});

		await fireEvent.click(screen.getByRole('button', { name: /프로젝트 선택/ }));
		expect(screen.getByRole('listbox')).toBeTruthy();

		await fireEvent.pointerDown(document.body);
		expect(screen.queryByRole('listbox')).toBeNull();
	});
});
