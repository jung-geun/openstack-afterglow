import { writable, get } from 'svelte/store';
import { env } from '$env/dynamic/public';

interface SiteConfig {
	site_name: string;
	site_description: string;
}

const DEFAULTS: SiteConfig = {
	site_name: 'Union',
	site_description: 'OpenStack VM + OverlayFS 배포 플랫폼',
};

export const siteConfig = writable<SiteConfig>({ ...DEFAULTS });

export async function loadSiteConfig(): Promise<void> {
	// 환경변수가 설정되어 있으면 API 호출 없이 사용
	const nameFromEnv = env.PUBLIC_SITE_NAME;
	const descFromEnv = env.PUBLIC_SITE_DESCRIPTION;
	if (nameFromEnv || descFromEnv) {
		siteConfig.set({
			site_name: nameFromEnv || DEFAULTS.site_name,
			site_description: descFromEnv || DEFAULTS.site_description,
		});
		return;
	}
	try {
		const apiBase = typeof window !== 'undefined'
			? (env.PUBLIC_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`)
			: (env.PUBLIC_API_BASE || 'http://backend:8000');
		const res = await fetch(`${apiBase}/api/site-config`);
		if (res.ok) {
			const data: SiteConfig = await res.json();
			siteConfig.set(data);
		}
	} catch {
		// 네트워크 오류 시 기본값 유지
	}
}

export function getSiteName(): string {
	return get(siteConfig).site_name;
}

export function getSiteDescription(): string {
	return get(siteConfig).site_description;
}
