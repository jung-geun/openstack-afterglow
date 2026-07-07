import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import SelectionCheckbox from '../SelectionCheckbox.svelte';

function checkbox() {
	return screen.getByRole('checkbox', { name: '인스턴스 선택' }) as HTMLInputElement;
}

describe('SelectionCheckbox', () => {
	it('renders an accessible checkbox control', () => {
		render(SelectionCheckbox, { ariaLabel: '인스턴스 선택' });
		expect(checkbox()).toBeTruthy();
		expect(checkbox().checked).toBe(false);
	});

	it('reflects checked and indeterminate states', () => {
		const { rerender } = render(SelectionCheckbox, { ariaLabel: '인스턴스 선택', checked: true });
		expect(checkbox().checked).toBe(true);

		rerender({ ariaLabel: '인스턴스 선택', checked: false, indeterminate: true });
		expect(checkbox().checked).toBe(false);
		expect(checkbox().indeterminate).toBe(true);
	});

	it('forwards click events to the caller', async () => {
		const onclick = vi.fn();
		render(SelectionCheckbox, { ariaLabel: '인스턴스 선택', onclick });
		checkbox().click();
		expect(onclick).toHaveBeenCalledOnce();
	});
});
