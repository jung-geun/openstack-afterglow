import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import PageHeader from '../PageHeader.svelte';

describe('PageHeader', () => {
	it('breadcrumb 텍스트 렌더링', () => {
		render(PageHeader, { breadcrumb: 'OVERVIEW', title: 'Test' });
		expect(screen.getByText('OVERVIEW')).toBeTruthy();
	});

	it('title이 h1으로 렌더링', () => {
		render(PageHeader, { breadcrumb: 'NAV', title: '인스턴스 목록' });
		const h1 = screen.getByRole('heading', { level: 1 });
		expect(h1.textContent).toBe('인스턴스 목록');
	});

	it('subtitle이 있으면 렌더링', () => {
		render(PageHeader, { breadcrumb: 'NAV', title: 'T', subtitle: '설명 텍스트' });
		expect(screen.getByText('설명 텍스트')).toBeTruthy();
	});

	it('subtitle이 없으면 p 요소 없음', () => {
		const { container } = render(PageHeader, { breadcrumb: 'NAV', title: 'T' });
		expect(container.querySelector('p')).toBeNull();
	});
});
