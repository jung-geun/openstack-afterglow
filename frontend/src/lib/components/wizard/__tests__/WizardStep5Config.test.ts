import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	apiGet: vi.fn(),
	apiPost: vi.fn(),
	apiDelete: vi.fn(),
}));

vi.mock('$lib/api/client', () => ({
	api: { get: mocks.apiGet, post: mocks.apiPost, delete: mocks.apiDelete },
	ApiError: class ApiError extends Error {},
}));
vi.mock('$lib/stores/vmCreateStore.svelte', () => ({
	useVmCreate: () => ({
		adminMode: false,
		githubSshEligible: false,
		keypairs: [{ name: 'test-keypair' }],
		networks: [],
		securityGroups: [],
		defaultNetworkId: null,
		fileStorages: [],
		selectNetwork: vi.fn(),
		selectSshAccessMode: vi.fn(),
	}),
}));

import WizardStep5Config from '../WizardStep5Config.svelte';
import { auth } from '$lib/stores/auth';
import { resetWizard, wizard } from '$lib/stores/wizard';

describe('WizardStep5Config cloud-init library', () => {
	beforeEach(() => {
		resetWizard();
		wizard.update(w => ({
			...w,
			bootSource: 'image',
			imageId: 'image-a',
			cloudInit: '#cloud-config\npackages: [htop]',
			keyName: 'test-keypair',
		}));
		auth.set({
			token: 'test-token',
			refreshToken: null,
			accessExpiresAt: null,
			userId: 'user-a',
			username: 'user-a',
			projectId: 'project-a',
			projectName: 'Project A',
			availableProjects: [],
			roles: [],
			isSystemAdmin: false,
			federated: false,
		});
		mocks.apiGet.mockReset();
		mocks.apiPost.mockReset();
		mocks.apiDelete.mockReset();
		mocks.apiPost.mockResolvedValue({ id: 1 });
	});

	it('loads a saved snippet into cloud-init and saves the edited content as a preset', async () => {
		mocks.apiGet.mockResolvedValue({
			history: [],
			presets: [{
				id: 1,
				kind: 'preset',
				name: 'bootstrap',
				content: '#cloud-config\npackages: [git]',
				created_at: '2026-07-20T00:00:00+00:00',
			}],
		});
		const { container } = render(WizardStep5Config);

		await waitFor(() => expect(mocks.apiGet).toHaveBeenCalledWith(
			'/api/v1/instances/cloud-init/library', 'test-token', 'project-a',
		));
		await fireEvent.change(screen.getByLabelText('저장된 항목 불러오기'), { target: { value: '1' } });
		expect((container.querySelector('textarea') as HTMLTextAreaElement).value).toContain('packages: [git]');

		await fireEvent.input(screen.getByLabelText('저장 이름'), { target: { value: 'git setup' } });
		await fireEvent.click(screen.getByRole('button', { name: '현재 내용 저장' }));
		await waitFor(() => expect(mocks.apiPost).toHaveBeenCalledWith(
			'/api/v1/instances/cloud-init/presets',
			{ name: 'git setup', content: '#cloud-config\npackages: [git]' },
			'test-token',
			'project-a',
		));
	});
});
