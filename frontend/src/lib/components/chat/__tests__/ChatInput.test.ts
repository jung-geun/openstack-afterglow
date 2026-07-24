import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$lib/api/chatAttachments', async (importOriginal) => {
	const actual = await importOriginal<typeof import('$lib/api/chatAttachments')>();
	return { ...actual, uploadChatAttachment: vi.fn() };
});

import ChatInput from '../ChatInput.svelte';
import { uploadChatAttachment } from '$lib/api/chatAttachments';

beforeEach(() => {
	vi.mocked(uploadChatAttachment).mockReset();
	Object.defineProperty(URL, 'createObjectURL', {
		configurable: true,
		value: vi.fn(() => 'blob:preview')
	});
	Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
});

describe('ChatInput attachments', () => {
	it('marks a scanned image ready instead of leaving the composer upload-blocked', async () => {
		vi.mocked(uploadChatAttachment).mockResolvedValue({
			id: 'asset-clean',
			mime_type: 'image/png',
			name: 'clean.png'
		});
		const { container } = render(ChatInput, {
			value: '',
			modelCaps: { vision: true },
			onSend: vi.fn(),
			onStop: vi.fn()
		});
		const input = container.querySelector<HTMLInputElement>('input[type="file"]');
		expect(input).toBeTruthy();
		const file = new File(['image'], 'clean.png', { type: 'image/png' });
		Object.defineProperty(input!, 'files', { configurable: true, value: [file] });

		await fireEvent.change(input!);

		await waitFor(() => expect(container.querySelector('.chip.uploading')).toBeNull());
		expect(container.querySelector<HTMLImageElement>('.chip img')?.alt).toBe('clean.png');
	});

	it('explains when the scanned asset pipeline is unavailable', () => {
		const { container } = render(ChatInput, {
			value: '',
			modelCaps: {
				vision: true,
				feature_gates: {
					image_input: {
						available: false,
						mode: 'none',
						reason_code: 'asset_pipeline_unavailable',
						pricing_available: false
					}
				}
			},
			onSend: vi.fn(),
			onStop: vi.fn()
		});

		expect(container.querySelector<HTMLButtonElement>('.tool-shell')?.disabled).toBe(true);
		expect(container.querySelector('.plus')?.getAttribute('title')).toBe(
			'첨부 저장소와 보안 검사기가 설정되지 않았습니다. 관리자에게 문의하세요.'
		);
	});
});
