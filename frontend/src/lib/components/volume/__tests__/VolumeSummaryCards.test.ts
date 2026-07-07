import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import VolumeSummaryCards from '../VolumeSummaryCards.svelte';
import type { Snapshot, Volume } from '$lib/types/volume';

const volumes: Volume[] = [
	{
		id: 'vol-1',
		name: 'volume-1',
		status: 'available',
		size: 10,
		volume_type: null,
		attachments: [],
	},
];

const snapshots: Snapshot[] = [
	{
		id: 'snap-1',
		name: 'snapshot-1',
		status: 'available',
		volume_id: 'vol-1',
		size: 10,
		description: '',
		created_at: new Date().toISOString(),
	},
];

const quotas = {
	storage: {
		volumes: { limit: 5, in_use: 1 },
		gigabytes: { limit: 100, in_use: 10 },
	},
};

describe('VolumeSummaryCards', () => {
	it('renders snapshot summary by default', () => {
		render(VolumeSummaryCards, { volumes, snapshots, quotas });

		expect(screen.getByText('스냅샷')).toBeTruthy();
		expect(screen.getByText('최근 24시간 1개')).toBeTruthy();
	});

	it('hides snapshot summary and switches to two columns when snapshot beta is off', () => {
		const { container } = render(VolumeSummaryCards, {
			volumes,
			snapshots,
			quotas,
			showSnapshots: false,
		});

		expect(screen.queryByText('스냅샷')).toBeNull();
		expect(screen.queryByText('최근 24시간 1개')).toBeNull();
		expect(container.firstElementChild?.classList.contains('grid-cols-2')).toBe(true);
		expect(container.firstElementChild?.classList.contains('grid-cols-3')).toBe(false);
	});
});
