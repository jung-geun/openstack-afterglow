import { describe, expect, it } from 'vitest';

import { nextSquashfsSelection } from '../vmCreateStore.svelte';

const empty = { squashfsMode: null, layerProfileName: null, layerArtifactIds: [] };

describe('nextSquashfsSelection', () => {
	it('clears a profile when it is selected again', () => {
		const selected = nextSquashfsSelection(empty, { type: 'profile', name: 'ml-stack' });
		expect(nextSquashfsSelection(selected, { type: 'profile', name: 'ml-stack' })).toEqual(empty);
	});

	it('clears an active mode when it is selected again', () => {
		const selected = nextSquashfsSelection(empty, { type: 'mode', mode: 'artifacts' });
		expect(nextSquashfsSelection(selected, { type: 'mode', mode: 'artifacts' })).toEqual(empty);
	});

	it('returns to ordinary VM mode when the final artifact is removed', () => {
		const selected = nextSquashfsSelection(empty, { type: 'artifact', id: 7, lineageIds: [1, 7] });
		expect(nextSquashfsSelection(selected, { type: 'artifact', id: 7, lineageIds: [1, 7] })).toEqual({
			squashfsMode: 'artifacts',
			layerProfileName: null,
			layerArtifactIds: [1],
		});
		expect(nextSquashfsSelection({ squashfsMode: 'artifacts', layerProfileName: null, layerArtifactIds: [7] }, { type: 'artifact', id: 7, lineageIds: [7] })).toEqual(empty);
	});
});
