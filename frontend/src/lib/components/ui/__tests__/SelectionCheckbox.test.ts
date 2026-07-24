import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import SelectionCheckbox from '../SelectionCheckbox.svelte';
import SelectionCheckboxHarness from './SelectionCheckboxHarness.svelte';

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

	it('renders an unavailable mark for a permanently ineligible resource', () => {
		render(SelectionCheckbox, {
			ariaLabel: '인스턴스 선택',
			disabled: true,
			unavailable: true,
			title: '연결된 볼륨은 선택할 수 없습니다.',
		});
		expect(checkbox().disabled).toBe(true);
		expect(checkbox().getAttribute('title')).toBe('연결된 볼륨은 선택할 수 없습니다.');
		expect(checkbox().closest('label')?.querySelector('.selection-unavailable')).toBeTruthy();
		expect(checkbox().closest('label')?.querySelector('.selection-box')).toBeNull();
	});

	it('keeps its checkbox shape while transiently disabled', () => {
		render(SelectionCheckbox, { ariaLabel: '선택', checked: true, disabled: true });
		const busyCheckbox = screen.getByRole('checkbox', { name: '선택' });
		expect(busyCheckbox.closest('label')?.querySelector('.selection-box')).toBeTruthy();
		expect(busyCheckbox.closest('label')?.querySelector('.selection-unavailable')).toBeNull();
	});

	it('does not bubble a disabled label click to a clickable resource surface', async () => {
		const onSurfaceClick = vi.fn();
		render(SelectionCheckboxHarness, { disabled: true, onSurfaceClick });

		await fireEvent.click(checkbox().closest('label')!);
		expect(onSurfaceClick).not.toHaveBeenCalled();
	});

	it('toggles without activating a Svelte resource surface', async () => {
		const onSurfaceClick = vi.fn();
		const onCheckboxClick = vi.fn();
		render(SelectionCheckboxHarness, { onSurfaceClick, onCheckboxClick });

		await fireEvent.click(checkbox().closest('label')!);
		expect(onCheckboxClick).toHaveBeenCalledOnce();
		expect(onSurfaceClick).not.toHaveBeenCalled();
	});

	it('stops a native resource surface listener before it can navigate', async () => {
		const onSurfaceClick = vi.fn();
		const onCheckboxClick = vi.fn();
		const { container } = render(SelectionCheckbox, {
			ariaLabel: '인스턴스 선택',
			onclick: onCheckboxClick,
		});
		const surface = document.createElement('div');
		surface.addEventListener('click', onSurfaceClick);
		surface.append(container.firstElementChild!);
		document.body.append(surface);

		await fireEvent.click(checkbox());
		expect(onCheckboxClick).toHaveBeenCalledOnce();
		expect(onSurfaceClick).not.toHaveBeenCalled();
		surface.remove();
	});
});
