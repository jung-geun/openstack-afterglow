import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { ImageInfo } from '$lib/types/compute';
import ImageCard from '../ImageCard.svelte';

const image: ImageInfo = {
	id: 'image-1', name: 'ubuntu-image:latest', repository: 'ubuntu-image', tag: 'latest',
	status: 'active', owner: 'project-1', size: 1024,
};
function renderCard(overrides: Partial<{
	img: ImageInfo;
	selectable: boolean;
	selected: boolean;
	onSelect: (id: string) => void;
	onToggleSelect: () => void;
}> = {}) {
	return render(ImageCard, {
		img: image,
		isOwner: true,
		toggling: false,
		deleting: false,
		selectable: true,
		selected: false,
		selectionDisabled: false,
		onSelect: vi.fn(),
		onToggleSelect: vi.fn(),
		onToggleActivation: vi.fn(),
		onEdit: vi.fn(),
		onDelete: vi.fn(),
		...overrides,
	});
}

describe('ImageCard selection', () => {
	it('isolates checkbox click and keyboard activation from the detail button', async () => {
		const onSelect = vi.fn();
		const onToggleSelect = vi.fn();
		renderCard({ onSelect, onToggleSelect });
		const checkbox = screen.getByRole('checkbox', { name: 'ubuntu-image:latest 선택' });

		await fireEvent.click(checkbox.closest('label')!);
		checkbox.focus();
		await fireEvent.keyDown(checkbox, { key: 'Enter' });
		expect(onToggleSelect).toHaveBeenCalledOnce();
		expect(onSelect).not.toHaveBeenCalled();
	});

	it('shows a disabled checkbox for an image outside the current project', () => {
		renderCard({ selectable: false });
		expect((screen.getByRole('checkbox', { name: 'ubuntu-image:latest 선택' }) as HTMLInputElement).disabled).toBe(true);
	});
	it('shows the implicit latest tag when the API omits legacy tag fields', () => {
		renderCard({ img: { ...image, tag: undefined } });
		expect(screen.getByText('latest')).toBeTruthy();
	});
});
