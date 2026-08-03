import { fireEvent, render } from '@testing-library/svelte';
import { expect, it, vi } from 'vitest';
import InteractionCard from '../InteractionCard.svelte';

it('submits only the stored-option-shaped interaction response', async () => {
	const onResolve = vi.fn();
	const { getByLabelText, getByRole } = render(InteractionCard, {
		question: 'Continue?',
		options: [{ id: 'yes', label: 'Yes' }],
		allowText: true,
		onResolve
	});
	await fireEvent.click(getByLabelText('Yes'));
	await fireEvent.click(getByRole('button', { name: '응답 보내기' }));
	expect(onResolve).toHaveBeenCalledWith({ option_ids: ['yes'], text: null });
});
