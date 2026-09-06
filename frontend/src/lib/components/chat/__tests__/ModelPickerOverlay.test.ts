import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ModelPickerOverlay from '../ModelPickerOverlay.svelte';

const models = [
	{ id: 1, model_name: 'gpt-5', display_name: 'GPT 5', provider: 'OpenAI' },
	{ id: 2, model_name: 'claude-sonnet', display_name: 'Claude Sonnet', provider: 'Anthropic' },
	{ id: 3, model_name: 'gpt-4.1', display_name: 'GPT 4.1', provider: 'OpenAI' }
];

function renderPicker(availableModels = models) {
	return render(ModelPickerOverlay, {
		open: true,
		models: availableModels,
		value: 'gpt-5',
		onSelect: vi.fn(),
		onClose: vi.fn()
	});
}

describe('ModelPickerOverlay provider navigation', () => {
	it('shows a provider selector for multiple providers and filters the model list', async () => {
		const view = renderPicker();
		const navigation = view.getByRole('navigation', { name: '모델 프로바이더' });

		expect(view.getByRole('button', { name: 'GPT 5 모델 선택' })).toBeTruthy();
		expect(view.getByRole('button', { name: 'Claude Sonnet 모델 선택' })).toBeTruthy();
		await fireEvent.click(view.getByRole('button', { name: /OpenAI/ }));

		expect(navigation).toBeTruthy();
		expect(view.getByRole('button', { name: 'GPT 4.1 모델 선택' })).toBeTruthy();
		expect(view.queryByRole('button', { name: 'Claude Sonnet 모델 선택' })).toBeNull();
	});

	it('omits provider navigation when every model uses the same provider', () => {
		const view = renderPicker(models.filter((model) => model.provider === 'OpenAI'));

		expect(view.queryByRole('navigation', { name: '모델 프로바이더' })).toBeNull();
		expect(view.getByRole('button', { name: 'GPT 5 모델 선택' })).toBeTruthy();
	});

	it('keeps name and provider search filtering available', async () => {
		const view = renderPicker();

		await fireEvent.input(view.getByPlaceholderText('모델 검색 (이름·프로바이더)'), {
			target: { value: 'Anthropic' }
		});

		expect(view.getByRole('button', { name: 'Claude Sonnet 모델 선택' })).toBeTruthy();
		expect(view.queryByRole('button', { name: 'GPT 5 모델 선택' })).toBeNull();
	});
});
