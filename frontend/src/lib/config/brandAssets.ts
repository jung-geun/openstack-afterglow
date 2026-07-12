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
	_theme: ResolvedBrandTheme,
): string {
	// 파비콘은 브랜드 마크와 달리 테마 독립적으로 원래 favicon.ico를 유지한다.
	// _theme 파라미터는 호출부(+layout.svelte)/테스트 시그니처 호환을 위해 남겨둔다.
	return config.favicon_path || LEGACY_FAVICON_PATH;
}
