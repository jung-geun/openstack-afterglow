import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { ImageInfo } from '$lib/types/compute';
import SelectImage from '../SelectImage.svelte';

const images: ImageInfo[] = [
	{
		id: 'ubuntu-2204',
		name: 'ubuntu:22.04',
		repository: 'ubuntu',
		tag: '22.04',
		status: 'active',
		os_distro: 'ubuntu',
	},
	{
		id: 'ubuntu-2404',
		name: 'ubuntu:24.04',
		repository: 'ubuntu',
		tag: '24.04',
		status: 'active',
		os_distro: 'ubuntu',
	},
	{
		id: 'fedora-40',
		name: 'fedora:40',
		repository: 'fedora',
		tag: '40',
		status: 'active',
		os_distro: 'fedora',
	},
];

function renderSelector(onSelect = vi.fn()) {
	return { onSelect, ...render(SelectImage, { images, selectedId: null, onSelect }) };
}

describe('SelectImage', () => {
	it('searches canonical image names and tags', async () => {
		const { onSelect } = renderSelector();
		const search = screen.getByRole('searchbox', { name: '이미지 이름, tag, OS 검색' });

		await fireEvent.input(search, { target: { value: '24.04' } });

		expect(screen.getByRole('button', { name: 'ubuntu:24.04 이미지 선택' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'ubuntu:22.04 이미지 선택' })).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'ubuntu:24.04 이미지 선택' }));
		expect(onSelect).toHaveBeenCalledWith('ubuntu-2404', 'ubuntu:24.04');
	});

	it('filters the image grid by OS family before selecting a tag', async () => {
		renderSelector();

		await fireEvent.click(screen.getByRole('button', { name: 'Fedora 1' }));

		expect(screen.getByRole('button', { name: 'fedora:40 이미지 선택' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'ubuntu:22.04 이미지 선택' })).toBeNull();
		expect(screen.queryByRole('button', { name: 'ubuntu:24.04 이미지 선택' })).toBeNull();
	});

	it('keeps the source image name for version-aware library validation', async () => {
		const onSelect = vi.fn();
		render(SelectImage, {
			images: [{
				...images[0],
				id: 'ubuntu-raw-name',
				name: 'ubuntu-24.04-server',
				tag: 'latest',
			}],
			selectedId: null,
			onSelect,
		});

		expect(screen.getByText('Ubuntu 24.04 LTS')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'ubuntu:latest 이미지 선택' }));
		expect(onSelect).toHaveBeenCalledWith('ubuntu-raw-name', 'ubuntu-24.04-server');
	});

	it('normalizes legacy names when repository and tag fields are absent', async () => {
		const onSelect = vi.fn();
		render(SelectImage, {
			images: [{ ...images[0], id: 'legacy-ubuntu', name: 'ubuntu', repository: undefined, tag: undefined }],
			selectedId: null,
			onSelect,
		});

		const card = screen.getByRole('button', { name: 'ubuntu:latest 이미지 선택' });
		expect(card).toBeTruthy();
		await fireEvent.click(card);
		expect(onSelect).toHaveBeenCalledWith('legacy-ubuntu', 'ubuntu:latest');
	});
});
