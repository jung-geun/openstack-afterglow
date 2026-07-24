import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import CreateProjectDialog from '../CreateProjectDialog.svelte';

describe('CreateProjectDialog', () => {
	it('stays visible when Escape or the backdrop is used while creation is pending', async () => {
		let resolveCreate: (value: boolean) => void;
		const onCreate = vi.fn(
			() =>
				new Promise<boolean>((resolve) => {
					resolveCreate = resolve;
				})
		);
		const onClose = vi.fn();
		render(CreateProjectDialog, { open: true, onClose, onCreate });

		await fireEvent.input(screen.getByPlaceholderText('예: OpenStack 운영'), { target: { value: '운영' } });
		await fireEvent.click(screen.getByRole('button', { name: '프로젝트 만들기' }));
		await fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
		await fireEvent.click(screen.getByRole('dialog'));

		expect(screen.getByLabelText('프로젝트 만들기')).toBeTruthy();
		expect(onClose).not.toHaveBeenCalled();

		resolveCreate!(false);
		await waitFor(() => expect(screen.getByLabelText('프로젝트 만들기')).toBeTruthy());
	});
});
