import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
const { get, put } = apiMocks;

vi.mock('$lib/api/client', () => ({
	api: apiMocks,
	ApiError: class ApiError extends Error {}
}));

import AdminResourcePoliciesPanel from '../AdminResourcePoliciesPanel.svelte';

describe('AdminResourcePoliciesPanel', () => {
	beforeEach(() => {
		get.mockReset();
		put.mockReset();
		get.mockResolvedValueOnce([
			{
				key: 'builder.image',
				resource_kind: 'image',
				title: 'Layer builder image',
				external_only: false,
				resource_id: null,
				resource_name: null
			}
		]).mockResolvedValueOnce({ options: [{ id: 'image-1', name: 'Ubuntu' }] });
		put.mockResolvedValue({ key: 'builder.image', resource_id: 'image-1', resource_name: 'Ubuntu' });
	});

	it('discovers an admin-scoped catalog and persists only the selected ID', async () => {
		render(AdminResourcePoliciesPanel, { token: 'token', projectId: 'admin-project' });
		await screen.findByText('Layer builder image');

		await fireEvent.click(screen.getByRole('button', { name: '목록 조회' }));
		await waitFor(() => expect(get).toHaveBeenCalledWith(
			'/api/v1/admin/resource-policies/catalog/builder.image',
			'token',
			'admin-project'
		));
		const select = await screen.findByLabelText('Layer builder image 선택');
		await fireEvent.change(select, { target: { value: 'image-1' } });
		await fireEvent.click(screen.getByRole('button', { name: '저장' }));

		await waitFor(() => expect(put).toHaveBeenCalledWith(
			'/api/v1/admin/resource-policies/builder.image',
			{ resource_id: 'image-1' },
			'token',
			'admin-project'
		));
	});
});
