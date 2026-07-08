import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import BulkSelectionOverlay from '../BulkSelectionOverlay.svelte';

const handlers = () => ({
	onStart: vi.fn(),
	onStop: vi.fn(),
	onDelete: vi.fn(),
	onClear: vi.fn(),
});

describe('BulkSelectionOverlay', () => {
	it('does not render when no rows are selected', () => {
		render(BulkSelectionOverlay, { count: 0, ...handlers() });
		expect(screen.queryByRole('region', { name: '선택한 인스턴스 일괄 작업' })).toBeNull();
	});

	it('renders fixed bulk actions when rows are selected', () => {
		render(BulkSelectionOverlay, { count: 3, ...handlers() });
		expect(screen.getByText('3')).toBeTruthy();
		expect(screen.getByRole('button', { name: '시작' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '종료' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '삭제' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '취소' })).toBeTruthy();
	});

	it('forwards bulk action clicks', async () => {
		const actions = handlers();
		render(BulkSelectionOverlay, { count: 1, ...actions });
		await fireEvent.click(screen.getByRole('button', { name: '시작' }));
		await fireEvent.click(screen.getByRole('button', { name: '종료' }));
		await fireEvent.click(screen.getByRole('button', { name: '삭제' }));
		await fireEvent.click(screen.getByRole('button', { name: '취소' }));
		expect(actions.onStart).toHaveBeenCalledOnce();
		expect(actions.onStop).toHaveBeenCalledOnce();
		expect(actions.onDelete).toHaveBeenCalledOnce();
		expect(actions.onClear).toHaveBeenCalledOnce();
	});
});
