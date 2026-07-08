import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import type { AdminInstance } from '$lib/types/adminInstance';

vi.mock('$lib/stores/projectNames', () => ({
	projectNames: {
		subscribe: (run: (value: Map<string, string>) => void) => {
			run(new Map([['project-1', 'Project One']]));
			return () => {};
		},
		load: vi.fn(),
		reset: vi.fn(),
	},
}));

import AdminInstanceTable from '../instances/AdminInstanceTable.svelte';

describe('AdminInstanceTable', () => {
	it('keeps content interactive while refreshing', async () => {
		const instance: AdminInstance = {
			id: 'inst-1',
			name: 'vm-one',
			status: 'ACTIVE',
			project_id: 'project-1',
			user_id: 'user-1',
			flavor: 'm1.small',
			host: 'host-1',
			created_at: '2026-06-01T00:00:00Z',
		};
		const onOpen = vi.fn();

		const { container } = render(AdminInstanceTable, {
			props: {
				refreshing: true,
				instances: [instance],
				markerStack: [],
				nextMarker: null,
				selectedIds: new Set<string>(),
				onOpen,
				onPrev: vi.fn(),
				onNext: vi.fn(),
				onToggleSelect: vi.fn(),
				onToggleAll: vi.fn(),
			},
		});

		expect(container.querySelector('.opacity-60')).toBeNull();
		expect(container.querySelector('.pointer-events-none')).toBeNull();

		await fireEvent.click(screen.getByRole('button', { name: 'vm-one' }));
		expect(onOpen).toHaveBeenCalledTimes(1);
		expect(onOpen).toHaveBeenCalledWith(instance);
	});
});
