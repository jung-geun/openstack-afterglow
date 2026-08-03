import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import Pagination from '../Pagination.svelte';

describe('Pagination intent', () => {
	it('warms enabled next navigation on pointer entry without clicking', async () => {
		const onNext = vi.fn();
		const onintent = vi.fn();
		render(Pagination, {
			page: 1,
			hasPrev: false,
			hasNext: true,
			onPrev: vi.fn(),
			onNext,
			onintent,
		});

		await fireEvent.pointerEnter(screen.getByRole('button', { name: '다음 →' }));
		expect(onNext).not.toHaveBeenCalled();
		expect(onintent).toHaveBeenCalledOnce();
	});

	it('never emits intent from previous or disabled next navigation', async () => {
		const onintent = vi.fn();
		render(Pagination, {
			page: 2,
			hasPrev: true,
			hasNext: false,
			onPrev: vi.fn(),
			onNext: vi.fn(),
			onintent,
		});

		await fireEvent.focus(screen.getByRole('button', { name: '← 이전' }));
		await fireEvent.pointerEnter(screen.getByRole('button', { name: '다음 →' }));
		expect(onintent).not.toHaveBeenCalled();
	});
});
