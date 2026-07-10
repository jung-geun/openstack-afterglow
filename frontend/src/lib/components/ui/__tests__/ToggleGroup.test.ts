import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import ToggleGroup from '../ToggleGroup.svelte';

describe('ToggleGroup', () => {
	const options = [
		{ value: '10', label: '10' },
		{ value: '20', label: '20' },
	];

	it('renders options and marks the active option pressed', () => {
		render(ToggleGroup, { value: '10', options, onchange: vi.fn() });
		expect(screen.getByRole('button', { name: '10' }).getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByRole('button', { name: '10' }).classList.contains('toggle-selected')).toBe(true);
		expect(screen.getByRole('button', { name: '20' }).getAttribute('aria-pressed')).toBe('false');
	});

	it('exposes an accessible name for the toggle group', () => {
		render(ToggleGroup, { value: '10', options, onchange: vi.fn(), ariaLabel: '워크플로우 필터' });
		expect(screen.getByRole('group', { name: '워크플로우 필터' })).toBeTruthy();
	});

	it('calls onchange once with the clicked option value', async () => {
		const onchange = vi.fn();
		render(ToggleGroup, { value: '10', options, onchange });
		await fireEvent.click(screen.getByRole('button', { name: '20' }));
		expect(onchange).toHaveBeenCalledTimes(1);
		expect(onchange).toHaveBeenCalledWith('20');
	});
});
