import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import BetaFeatureGate from '../BetaFeatureGate.svelte';

describe('BetaFeatureGate', () => {
	it('renders the title and links to account beta settings', () => {
		render(BetaFeatureGate, { title: 'Key Manager는 베타 기능입니다' });

		expect(screen.getByText('Key Manager는 베타 기능입니다')).toBeTruthy();
		const link = screen.getByRole('link', { name: '베타 설정으로 이동' });
		expect(link.getAttribute('href')).toBe('/dashboard/account');
	});
});
