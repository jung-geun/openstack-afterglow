import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import SelectionToolbar from '../SelectionToolbar.svelte';

describe('SelectionToolbar', () => {
	it('renders the checked, indeterminate selection state and count', () => {
		render(SelectionToolbar, {
			label: '볼륨',
			ariaLabel: '볼륨 선택',
			checked: false,
			indeterminate: true,
			selectedCount: 2,
			onToggle: vi.fn(),
		});
		const checkbox = screen.getByRole('checkbox', { name: '전체 볼륨 선택' }) as HTMLInputElement;
		expect(checkbox.checked).toBe(false);
		expect(checkbox.indeterminate).toBe(true);
		expect(screen.getByText('전체 선택')).toBeTruthy();
		expect(screen.getByText('2개 선택됨')).toBeTruthy();
	});

	it('invokes the supplied toggle callback', async () => {
		const onToggle = vi.fn();
		render(SelectionToolbar, {
			label: '볼륨',
			ariaLabel: '볼륨 선택',
			checked: true,
			indeterminate: false,
			selectedCount: 3,
			onToggle,
		});
		await fireEvent.click(screen.getByRole('checkbox', { name: '전체 볼륨 선택' }));
		expect(onToggle).toHaveBeenCalledOnce();
	});
});
