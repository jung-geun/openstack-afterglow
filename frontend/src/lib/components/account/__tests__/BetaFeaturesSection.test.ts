import { get } from 'svelte/store';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));

import BetaFeaturesSection from '../BetaFeaturesSection.svelte';
import { betaFeatures } from '$lib/stores/betaFeatures';

describe('BetaFeaturesSection', () => {
	beforeEach(() => {
		localStorage.clear();
		betaFeatures.set({ libraryConsume: false, haDeploy: false });
	});

	it('renders per-browser beta feature guidance', () => {
		render(BetaFeaturesSection);

		expect(screen.getByText('베타 기능')).toBeTruthy();
		expect(
			screen.getByText('이 설정은 현재 브라우저에만 저장됩니다. 프로젝트 전체 서버 설정이나 다른 사용자에게는 적용되지 않습니다.'),
		).toBeTruthy();
	});

	it('toggles and persists both beta feature flags', async () => {
		render(BetaFeaturesSection);

		const squashfsToggle = screen.getByRole('checkbox', {
			name: /squashfs 라이브러리 소비 VM 생성 단계 표시/i,
		}) as HTMLInputElement;
		const haToggle = screen.getByRole('checkbox', {
			name: /HA 배포 옵션 표시/i,
		}) as HTMLInputElement;

		expect(squashfsToggle.checked).toBe(false);
		expect(haToggle.checked).toBe(false);

		await fireEvent.click(squashfsToggle);
		await fireEvent.click(haToggle);

		expect(get(betaFeatures)).toEqual({ libraryConsume: true, haDeploy: true });
		expect(squashfsToggle.checked).toBe(true);
		expect(haToggle.checked).toBe(true);
		expect(localStorage.getItem('afterglow.beta.libraryConsume')).toBe('true');
		expect(localStorage.getItem('afterglow.beta.haDeploy')).toBe('true');
	});
});
