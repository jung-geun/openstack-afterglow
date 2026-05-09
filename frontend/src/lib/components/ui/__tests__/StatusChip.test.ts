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
});
