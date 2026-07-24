import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import BulkSelectionOverlay, { type BulkSelectionAction } from '../BulkSelectionOverlay.svelte';

type OverlayTestProps = {
	count: number;
	ariaLabel: string;
	actions: BulkSelectionAction[];
	busy: boolean;
	onClear: () => void;
};

function props(overrides: Partial<OverlayTestProps> = {}): OverlayTestProps {
	const actions: BulkSelectionAction[] = [
		{ key: 'delete', label: '삭제', tone: 'danger', onAction: vi.fn() },
		{ key: 'activate', label: '활성화', tone: 'success', onAction: vi.fn(), disabled: true },
	];
	return {
		count: 2,
		ariaLabel: '선택한 볼륨 일괄 작업',
		actions,
		busy: false,
		onClear: vi.fn(),
		...overrides,
	};
}

describe('BulkSelectionOverlay', () => {
	it('does not render when no rows are selected', () => {
		render(BulkSelectionOverlay, props({ count: 0 }));
		expect(screen.queryByRole('region', { name: '선택한 볼륨 일괄 작업' })).toBeNull();
	});

	it('renders arbitrary actions with the supplied region label and tone', () => {
		render(BulkSelectionOverlay, props());
		expect(screen.getByRole('region', { name: '선택한 볼륨 일괄 작업' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '삭제' })).toBeTruthy();
		expect((screen.getByRole('button', { name: '활성화' }) as HTMLButtonElement).disabled).toBe(true);
	});

	it('forwards enabled actions and clear clicks', async () => {
		const view = props();
		render(BulkSelectionOverlay, view);
		await fireEvent.click(screen.getByRole('button', { name: '삭제' }));
		await fireEvent.click(screen.getByRole('button', { name: '취소' }));
		expect(view.actions[0].onAction).toHaveBeenCalledOnce();
		expect(view.onClear).toHaveBeenCalledOnce();
	});

	it('marks the region busy and disables every control while executing', () => {
		render(BulkSelectionOverlay, props({ busy: true }));
		expect(screen.getByRole('region', { name: '선택한 볼륨 일괄 작업' }).getAttribute('aria-busy')).toBe('true');
		expect((screen.getByRole('button', { name: '삭제' }) as HTMLButtonElement).disabled).toBe(true);
		expect((screen.getByRole('button', { name: '취소' }) as HTMLButtonElement).disabled).toBe(true);
	});
});
