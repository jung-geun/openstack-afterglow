import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));

vi.mock('$lib/stores/auth', () => ({
	auth: {
		subscribe(run: (value: { token: string; projectId: string; isSystemAdmin: boolean }) => void) {
			run({ token: 'token', projectId: 'project', isSystemAdmin: true });
			return () => {};
		}
	}
}));
vi.mock('$lib/api/client', () => ({
	api: { get: mocks.get, post: mocks.post, patch: mocks.patch, put: vi.fn(), delete: vi.fn() },
	ApiError: class ApiError extends Error {}
}));
vi.mock('$lib/stores/confirm.svelte', () => ({ confirmDialog: vi.fn() }));
vi.mock('$lib/stores/toast', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const { get, post, patch } = mocks;

import ModelPage from '../models/+page.svelte';
import ProviderPage from '../+page.svelte';
import ToolPage from '../tools/+page.svelte';

const provider = {
	id: 1,
	name: 'OpenAI',
	provider_type: 'openai',
	api_base: null,
	has_api_key: true,
	models_dev_provider_id: 'openai',
	is_active: true,
	margin_multiplier: 1
};
const models = [
	{
		id: 10,
		provider_id: 1,
		model_name: 'openai/gpt-test',
		display_name: 'Test',
		is_active: true,
		input_price_per_million: '2',
		output_price_per_million: '8',
		effective_input_price_per_million: '2',
		effective_output_price_per_million: '8',
		effective_price_source: 'models.dev',
		models_dev_model_id: 'openai/gpt-test',
		price_source: 'models.dev'
	},
	{
		id: 11,
		provider_id: 1,
		model_name: 'openai/manual',
		display_name: 'Manual',
		is_active: true,
		input_price_per_million: '3',
		output_price_per_million: '9',
		models_dev_model_id: null,
		price_source: 'manual',
		effective_input_price_per_million: '3',
		effective_output_price_per_million: '9',
		effective_price_source: 'manual'
	},
	{
		id: 12,
		provider_id: 1,
		model_name: 'gpt-5.4',
		display_name: null,
		is_active: true,
		input_price_per_million: null,
		output_price_per_million: null,
		effective_input_price_per_million: '5.000000',
		effective_output_price_per_million: '22.500000',
		effective_price_source: 'litellm',
		models_dev_model_id: null,
		price_source: null
	}
];

function queueInitialLoads() {
	get.mockImplementation((path: string) => {
		if (path === '/api/v1/chat/admin/providers') return Promise.resolve(provider ? [provider] : []);
		if (path === '/api/v1/chat/admin/models') return Promise.resolve(models);
		if (path === '/api/v1/chat/admin/models/title') return Promise.resolve({ model_id: null });
		return Promise.resolve([]);
	});
}

describe('admin chat model pricing', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		queueInitialLoads();
	});

	it('renders price values and their source', async () => {
		render(ModelPage);
		await screen.findByText('models.dev');
		expect(screen.getByText('수동')).toBeTruthy();
		expect(screen.getByText(/입력 2 · 출력 8 USD/)).toBeTruthy();
		expect(screen.getByText(/입력 5 · 출력 22\.5 USD/)).toBeTruthy();
	});

	it('offers Perplexity as a LiteLLM provider', async () => {
		render(ProviderPage);
		expect(await screen.findByRole('option', { name: 'Perplexity (Sonar)' })).toBeTruthy();
	});

	it('isolates MCP, skills, and custom HTTP tools on the tool settings route', async () => {
		render(ToolPage);
		expect(await screen.findByText('원격 MCP 서버')).toBeTruthy();
		expect(screen.getByText('커스텀 HTTP 툴')).toBeTruthy();
		expect(screen.getByText('스킬')).toBeTruthy();
		expect(screen.queryByText('LLM 프로바이더')).toBeNull();
	});

	it('saves a complete manual price pair with PATCH', async () => {
		render(ModelPage);
		await screen.findAllByText('가격 수정');
		await fireEvent.click(screen.getAllByText('가격 수정')[0]);
		const modal = screen.getByText('모델 가격 수정').parentElement!;
		const inputs = within(modal).getAllByPlaceholderText(/USD \/ 1M tokens/);
		await fireEvent.input(inputs[0], { target: { value: '3' } });
		await fireEvent.input(inputs[1], { target: { value: '9' } });
		await fireEvent.click(screen.getByText('저장'));
		await waitFor(() => expect(patch).toHaveBeenCalledWith('/api/v1/chat/admin/models/10', {
			input_price_per_million: '3', output_price_per_million: '9'
		}, 'token', 'project'));
	});

	it('preselects an exact catalog match but preserves manual prices', async () => {
		get.mockImplementation((path: string) => {
			if (path.startsWith('/api/v1/chat/admin/models/pricing/models-dev/providers?')) return Promise.resolve({ providers: [{ id: 'openai', name: 'OpenAI', model_count: 2 }] });
			if (path.includes('/pricing/models-dev/providers/openai')) return Promise.resolve({ models: [
				{ id: 'openai/gpt-test', name: 'GPT Test', input_price_per_million: '2', output_price_per_million: '8', price_available: true, unsupported_price_fields: ['cost.tiers'] },
				{ id: 'openai/manual', name: 'Manual', input_price_per_million: '2', output_price_per_million: '8', price_available: true, unsupported_price_fields: [] }
			] });
			if (path === '/api/v1/chat/admin/providers') return Promise.resolve([provider]);
			if (path === '/api/v1/chat/admin/models') return Promise.resolve(models);
			if (path === '/api/v1/chat/admin/models/title') return Promise.resolve({ model_id: null });
			return Promise.resolve([]);
		});
		render(ModelPage);
		await screen.findAllByText('models.dev 가격');
		await fireEvent.click(screen.getAllByText('models.dev 가격')[0]);
		await screen.findByText('models.dev 추천 가격');
		await screen.findByText(/수동 가격 보존/);
		const checkboxes = screen.getAllByRole('checkbox');
		expect(checkboxes.at(-3)?.checked).toBe(true);
		expect(checkboxes.at(-2)?.disabled).toBe(true);
		expect(screen.getByText(/tier\/cache\/reasoning\/audio 단가는 적용하지 않습니다/)).toBeTruthy();
	});

	it('searches only the registered catalog candidates', async () => {
		get.mockImplementation((path: string) => {
			if (path.startsWith('/api/v1/chat/admin/models/pricing/models-dev/providers?')) {
				return Promise.resolve({
					preferred_provider_ids: ['openai'],
					providers: [
						{ id: 'openai', name: 'OpenAI', model_count: 2 },
						{ id: 'anthropic', name: 'Anthropic', model_count: 15 }
					]
				});
			}
			if (path.includes('/pricing/models-dev/providers/openai')) return Promise.resolve({ models: [] });
			if (path.includes('/pricing/models-dev/providers/anthropic')) return Promise.resolve({ models: [] });
			if (path === '/api/v1/chat/admin/providers') return Promise.resolve([provider]);
			if (path === '/api/v1/chat/admin/models') return Promise.resolve(models);
			if (path === '/api/v1/chat/admin/models/title') return Promise.resolve({ model_id: null });
			return Promise.resolve([]);
		});
		render(ModelPage);
		await screen.findAllByText('models.dev 가격');
		await fireEvent.click(screen.getAllByText('models.dev 가격')[0]);
		const search = await screen.findByRole('searchbox', { name: '가격표 프로바이더 검색' });
		await fireEvent.input(search, { target: { value: 'anth' } });
		const providerSelect = screen.getByLabelText('가격표 프로바이더');
		await waitFor(() => expect(within(providerSelect).getByRole('option', { name: 'Anthropic (15)' })).toBeTruthy());
		expect(within(providerSelect).queryByRole('option', { name: 'OpenAI (2)' })).toBeNull();
		await fireEvent.input(search, { target: { value: 'missing' } });
		await screen.findByText('검색 조건에 맞는 가격표 프로바이더가 없습니다.');
		expect((screen.getByRole('button', { name: '선택 가격 적용' }) as HTMLButtonElement).disabled).toBe(true);
		expect(screen.queryByText('가격표를 불러오는 중…')).toBeNull();
	});

	it('requires an explicit catalog choice when the current provider has no match', async () => {
		get.mockImplementation((path: string) => {
			if (path.startsWith('/api/v1/chat/admin/models/pricing/models-dev/providers?')) {
				return Promise.resolve({
					preferred_provider_ids: [],
					providers: [{ id: 'anthropic', name: 'Anthropic', model_count: 15 }]
				});
			}
			if (path === '/api/v1/chat/admin/providers') {
				return Promise.resolve([{ ...provider, name: 'Custom gateway', provider_type: 'custom', models_dev_provider_id: null }]);
			}
			if (path === '/api/v1/chat/admin/models') return Promise.resolve(models);
			if (path === '/api/v1/chat/admin/models/title') return Promise.resolve({ model_id: null });
			return Promise.resolve([]);
		});
		render(ModelPage);
		await screen.findAllByText('models.dev 가격');
		await fireEvent.click(screen.getAllByText('models.dev 가격')[0]);
		const providerSelect = await screen.findByLabelText('가격표 프로바이더') as HTMLSelectElement;
		expect(providerSelect.value).toBe('');
		expect((screen.getByRole('button', { name: '선택 가격 적용' }) as HTMLButtonElement).disabled).toBe(true);
	});

	it('keeps the modal open and shows a concrete error when import fails', async () => {
		post.mockRejectedValueOnce(new Error('catalog unavailable'));
		get.mockImplementation((path: string) => {
			if (path.startsWith('/api/v1/chat/admin/models/pricing/models-dev/providers?')) return Promise.resolve({ providers: [{ id: 'openai', name: 'OpenAI', model_count: 1 }] });
			if (path.includes('/pricing/models-dev/providers/openai')) return Promise.resolve({ models: [{ id: 'openai/gpt-test', name: 'GPT Test', input_price_per_million: '2', output_price_per_million: '8', price_available: true, unsupported_price_fields: [] }] });
			if (path === '/api/v1/chat/admin/providers') return Promise.resolve([provider]);
			if (path === '/api/v1/chat/admin/models') return Promise.resolve(models);
			if (path === '/api/v1/chat/admin/models/title') return Promise.resolve({ model_id: null });
			return Promise.resolve([]);
		});
		render(ModelPage);
		await screen.findByText('Test');
		await fireEvent.click(screen.getByText('models.dev 가격'));
		await screen.findByText('선택 가격 적용');
		await fireEvent.click(screen.getByText('선택 가격 적용'));
		await screen.findByText('가격 import 실패');
		expect(screen.getByText('models.dev 추천 가격')).toBeTruthy();
	});
});
