import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
const { get, put } = apiMocks;

vi.mock('$lib/api/client', () => ({
	api: apiMocks,
	ApiError: class ApiError extends Error {}
}));

import AdminResourcePoliciesPanel from '../AdminResourcePoliciesPanel.svelte';

describe('AdminResourcePoliciesPanel', () => {
	let builderOptions: Array<{ id: string; name: string }>;

	beforeEach(() => {
		document.cookie = 'afterglow_resource_policy_draft=; path=/; max-age=0';
		get.mockReset();
		put.mockReset();
		builderOptions = [
			{ id: 'flavor-1', name: 'CPU build' },
			{ id: 'flavor-2', name: 'GPU build' }
		];
		get.mockImplementation((path: string) => {
			if (path === '/api/v1/admin/resource-policies') {
				return Promise.resolve([
					{
						key: 'builder.flavor',
						resource_kind: 'flavor',
						title: 'Builder flavor',
						group: 'Builder',
						help_text: 'Default flavor for service-project builds.',
						execution_scope: 'service',
						dependency: null,
						required_when: null,
						external_only: false,
						shared_only: false,
						state: 'missing',
						resource_id: null,
						resource_name: null
					}
				]);
			}
			if (path === '/api/v1/admin/runtime-settings') {
				return Promise.resolve([
					{
						key: 'k3s.version',
						title: 'K3s version',
						help_text: 'Version used for new K3s clusters.',
						value: 'v1.32.0+k3s1',
						state: 'configured'
					}
				]);
			}
			if (path.endsWith('/catalog/builder.flavor')) {
				return Promise.resolve({ options: builderOptions });
			}
			if (path.includes('/catalog/')) {
				return Promise.resolve({ options: [] });
			}
			return Promise.resolve([]);
		});
		put.mockResolvedValue({ key: 'builder.flavor', resource_id: 'flavor-1', resource_name: 'CPU build' });
	});

	it('discovers an admin-scoped catalog and persists only the selected ID', async () => {
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });
		const search = screen.getByLabelText('Builder flavor 검색 및 선택');

		await fireEvent.focus(search);
		await waitFor(() => expect(get).toHaveBeenCalledWith(
			'/api/v1/admin/resource-policies/catalog/builder.flavor',
			'token',
			'admin-project'
		));
		await fireEvent.click(await screen.findByRole('option', { name: /CPU build/ }));
		expect(document.cookie).toContain('builder.flavor');

		const policyRow = search.closest('.policy-row') as HTMLElement | null;
		if (!policyRow) throw new Error('Builder flavor policy row was not rendered');
		await fireEvent.click(within(policyRow).getByRole('button', { name: '저장' }));

		await waitFor(() => expect(put).toHaveBeenCalledWith(
			'/api/v1/admin/resource-policies/builder.flavor',
			{ resource_id: 'flavor-1' },
			'token',
			'admin-project'
		));
		await waitFor(() => expect(document.cookie).not.toContain('builder.flavor'));
	});

	it('selects the only discovered catalog option as an unsaved default', async () => {
		builderOptions = [{ id: 'flavor-only', name: 'Only flavor' }];
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });

		await screen.findByDisplayValue('Only flavor');
		expect(document.cookie).toContain('flavor-only');
		expect(put).not.toHaveBeenCalled();
	});

	it('filters the unified search and selection control by resource name or ID', async () => {
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });
		const search = screen.getByLabelText('Builder flavor 검색 및 선택');

		await fireEvent.focus(search);
		await screen.findByRole('option', { name: /CPU build/ });
		await fireEvent.input(search, { target: { value: 'gpu' } });
		expect(screen.getByRole('option', { name: /GPU build/ })).toBeTruthy();
		expect(screen.queryByRole('option', { name: /CPU build/ })).toBeNull();

		await fireEvent.input(search, { target: { value: 'flavor-1' } });
		expect(screen.getByRole('option', { name: /CPU build/ })).toBeTruthy();
		expect(screen.queryByLabelText('Builder flavor 선택')).toBeNull();
	});
	it('requires a confirmed option before saving a free-form query', async () => {
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });
		const search = screen.getByLabelText('Builder flavor 검색 및 선택');

		await fireEvent.focus(search);
		await screen.findByRole('option', { name: /CPU build/ });
		await fireEvent.input(search, { target: { value: 'cpu' } });

		const policyRow = search.closest('.policy-row') as HTMLElement | null;
		if (!policyRow) throw new Error('Builder flavor policy row was not rendered');
		await fireEvent.click(within(policyRow).getByRole('button', { name: '저장' }));

		expect(put).not.toHaveBeenCalled();
		expect(screen.getByText(/목록에서 리소스를 선택한 뒤 저장하세요/)).toBeTruthy();
	});

	it('supports keyboard navigation and selection in the unified combobox', async () => {
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });
		const search = screen.getByLabelText('Builder flavor 검색 및 선택') as HTMLInputElement;

		await fireEvent.focus(search);
		await screen.findByRole('option', { name: /CPU build/ });
		await fireEvent.keyDown(search, { key: 'ArrowDown' });
		const cpuOption = screen.getByRole('option', { name: /CPU build/ });
		expect(search.getAttribute('aria-activedescendant')).toBe(cpuOption.id);

		await fireEvent.keyDown(search, { key: 'ArrowDown' });
		const gpuOption = screen.getByRole('option', { name: /GPU build/ });
		expect(search.getAttribute('aria-activedescendant')).toBe(gpuOption.id);
		await fireEvent.keyDown(search, { key: 'Enter' });

		expect(search.value).toBe('GPU build');
		expect(document.cookie).toContain('flavor-2');
		expect(screen.queryByRole('listbox')).toBeNull();
	});

	it.each([
		['null root', 'null'],
		['null scope', '{"admin-project":null}'],
		['null policies', '{"admin-project":{"policies":null,"runtime":{}}}'],
		['non-string values', '{"admin-project":{"policies":{"builder.flavor":42},"runtime":{"k3s.version":true}}}']
	])('ignores malformed draft cookie: %s', async (_name, rawCookie) => {
		document.cookie = `afterglow_resource_policy_draft=${encodeURIComponent(rawCookie)}; path=/`;
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });

		const search = screen.getByLabelText('Builder flavor 검색 및 선택') as HTMLInputElement;
		expect(search.value).toBe('');
		await screen.findByText('Builder flavor');
	});

});
