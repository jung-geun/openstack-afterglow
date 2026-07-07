import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import StatusChip from '../StatusChip.svelte';

describe('StatusChip', () => {
	it('status 텍스트 렌더링', () => {
		render(StatusChip, { status: 'active' });
		expect(screen.getByText('active')).toBeTruthy();
	});

	it('null status는 "—" 표시', () => {
		render(StatusChip, { status: null });
		expect(screen.getByText('—')).toBeTruthy();
	});

	it('undefined status는 "—" 표시', () => {
		render(StatusChip, { status: undefined });
		expect(screen.getByText('—')).toBeTruthy();
	});

	it('span 요소로 렌더링', () => {
		const { container } = render(StatusChip, { status: 'ACTIVE' });
		const chip = container.querySelector('span');
		expect(chip).not.toBeNull();
	});

	it('dot indicator가 포함됨', () => {
		const { container } = render(StatusChip, { status: 'active' });
		const spans = container.querySelectorAll('span');
		expect(spans.length).toBeGreaterThanOrEqual(2);
	});

	it('maps ACTIVE to success tone', () => {
		const { container } = render(StatusChip, { status: 'ACTIVE' });
		expect(container.querySelector('.chip-success')).toBeTruthy();
	});

	it('maps BUILD to warning tone with pulse', () => {
		const { container } = render(StatusChip, { status: 'BUILD' });
		const chip = container.querySelector('.chip-warning');
		expect(chip).toBeTruthy();
		expect(chip?.classList.contains('pulse')).toBe(true);
	});

	it('maps ERROR to danger tone', () => {
		const { container } = render(StatusChip, { status: 'ERROR' });
		expect(container.querySelector('.chip-danger')).toBeTruthy();
	});

	it('maps unknown statuses to neutral tone', () => {
		const { container } = render(StatusChip, { status: 'mystery' });
		expect(container.querySelector('.chip-neutral')).toBeTruthy();
	});
});
