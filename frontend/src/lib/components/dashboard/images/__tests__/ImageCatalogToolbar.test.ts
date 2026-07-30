import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ImageCatalogToolbar from '../ImageCatalogToolbar.svelte';

describe('ImageCatalogToolbar', () => {
	it('exposes repository and tag filters beside the search field', () => {
		render(ImageCatalogToolbar, {
			resultCount: 3,
			totalCount: 5,
			repositoryCount: 2,
			repositoryOptions: [{ value: 'ubuntu', label: 'ubuntu', count: 2 }],
			tagOptions: [{ value: '24.04', label: '24.04', count: 1 }],
		});

		expect(screen.getByRole('searchbox', { name: '이미지 repository 또는 tag 검색' })).toBeTruthy();
		expect(screen.getByRole('option', { name: 'ubuntu (2)' })).toBeTruthy();
		expect(screen.getByRole('option', { name: '24.04 (1)' })).toBeTruthy();
		expect(screen.getByText('3개 이미지 · 2개 repository')).toBeTruthy();
	});

	it('clears the active search without blocking filter controls', async () => {
		const onClear = vi.fn();
		render(ImageCatalogToolbar, { searchQuery: 'ubuntu', repositoryFilter: 'ubuntu', onClear });
		const input = screen.getByRole('searchbox', { name: '이미지 repository 또는 tag 검색' });
		expect(screen.getByRole('button', { name: '검색어 지우기' })).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: '검색어 지우기' }));
		expect((input as HTMLInputElement).value).toBe('');
		await fireEvent.click(screen.getByRole('button', { name: '필터 초기화' }));
		expect(onClear).toHaveBeenCalledOnce();
	});
});
