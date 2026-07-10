import type { PublicSiteConfig } from '$lib/types/siteConfig';

export type ResolvedBrandTheme = 'dark' | 'light';

const LEGACY_LOGO_PATHS: Record<string, true> = {
	'': true,
	'/logo.png': true,
	'/logo-white.png': true,
	'/logo-dark.png': true,
};
const LEGACY_FAVICON_PATH = '/favicon.ico';

const themeMarkPath: Record<ResolvedBrandTheme, string> = {
	dark: '/brand/afterglow-mark-light.svg',
	light: '/brand/afterglow-mark-dark.svg',
};

export function resolveLandingLogoPath(
	config: Pick<PublicSiteConfig, 'logo_path' | 'logo_dark_path' | 'logo_light_path'>,
	theme: ResolvedBrandTheme,
): string {
	const configuredPath = theme === 'dark'
		? (config.logo_light_path || config.logo_path)
		: (config.logo_dark_path || config.logo_path);
	return LEGACY_LOGO_PATHS[configuredPath] ? themeMarkPath[theme] : configuredPath;
}

export function resolveFaviconPath(
	config: Pick<PublicSiteConfig, 'favicon_path'>,
	theme: ResolvedBrandTheme,
): string {
	return config.favicon_path && config.favicon_path !== LEGACY_FAVICON_PATH
		? config.favicon_path
		: themeMarkPath[theme];
}
