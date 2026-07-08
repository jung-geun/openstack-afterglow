import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import type { PublicSiteConfig } from '$lib/types/siteConfig';
import { siteConfig } from '$lib/config/site';
import { theme, type ThemePreference } from '$lib/stores/theme';

import LoginBrandHeader from '../LoginBrandHeader.svelte';

const baseConfig: PublicSiteConfig = {
	site_name: 'Afterglow',
	site_description: 'OpenStack VM + OverlayFS 배포 플랫폼',
	logo_path: '/logo.png',
	logo_dark_path: '/logo-dark.png',
	logo_light_path: '/logo-white.png',
	favicon_path: '/favicon.ico',
	refresh_interval_ms: 5000,
	services: { magnum: false, manila: false, zun: false, k3s: false, trove: false, swift: false, barbican: false },
	runtime: {
		api_base: '',
		s3_base: '',
		grafana_base: '',
	},
};

function buildConfig(overrides: Partial<PublicSiteConfig> = {}): PublicSiteConfig {
	return {
		...baseConfig,
		...overrides,
		services: { ...baseConfig.services, ...(overrides.services ?? {}) },
		runtime: { ...baseConfig.runtime, ...(overrides.runtime ?? {}) },
	};
}

describe('LoginBrandHeader', () => {
	beforeEach(() => {
		theme.set('system');
		siteConfig.set(buildConfig());
	});

	it.each<{
		name: string;
		preference: ThemePreference;
		config: Partial<PublicSiteConfig>;
		expectedSrc: string;
	}>([
		{
			name: 'resolved dark theme prefers the light-background-safe logo',
			preference: 'dark',
			config: { logo_light_path: '/brand/login-light.png' },
			expectedSrc: '/brand/login-light.png',
		},
		{
			name: 'resolved light theme prefers the dark-background-safe logo',
			preference: 'light',
			config: { logo_dark_path: '/brand/login-dark.png' },
			expectedSrc: '/brand/login-dark.png',
		},
		{
			name: 'dark theme falls back to legacy logo_path when logo_light_path is missing',
			preference: 'dark',
			config: { logo_path: '/brand/legacy.png', logo_light_path: '' },
			expectedSrc: '/brand/legacy.png',
		},
		{
			name: 'light theme falls back to legacy logo_path when logo_dark_path is missing',
			preference: 'light',
			config: { logo_path: '/brand/legacy.png', logo_dark_path: '' },
			expectedSrc: '/brand/legacy.png',
		},
	])('$name', ({ preference, config, expectedSrc }) => {
		theme.set(preference);
		siteConfig.set(buildConfig(config));

		render(LoginBrandHeader);
		flushSync();

		expect(screen.getByRole('img', { name: 'Afterglow' }).getAttribute('src')).toBe(expectedSrc);
	});
});
