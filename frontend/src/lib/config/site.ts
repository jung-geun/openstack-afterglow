import { writable, get } from 'svelte/store';
import type { PublicSiteConfig } from '$lib/types/siteConfig';

export type SiteConfig = PublicSiteConfig & {
	logo_dark_path: string;
	logo_light_path: string;
};

const DEFAULTS: SiteConfig = {
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

export const siteConfig = writable<SiteConfig>({ ...DEFAULTS });

export function initSiteConfig(config: PublicSiteConfig): void {
	siteConfig.set({
		...DEFAULTS,
		...config,
		services: { ...DEFAULTS.services, ...config.services },
		runtime: { ...DEFAULTS.runtime, ...config.runtime },
	});
}

export function getSiteName(): string {
	return get(siteConfig).site_name;
}

export function getSiteDescription(): string {
	return get(siteConfig).site_description;
}
