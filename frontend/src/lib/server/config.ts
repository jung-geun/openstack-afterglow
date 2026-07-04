import { readFileSync } from 'fs';
import { parse } from 'smol-toml';

export interface PublicSiteConfig {
	site_name: string;
	site_description: string;
	logo_path: string;
	favicon_path: string;
	refresh_interval_ms: number;
	services: {
		magnum: boolean;
		manila: boolean;
		zun: boolean;
		k3s: boolean;
		trove: boolean;
		swift: boolean;
		barbican: boolean;
	};
}

const DEFAULTS: PublicSiteConfig = {
	site_name: 'Afterglow',
	site_description: 'OpenStack VM + OverlayFS 배포 플랫폼',
	logo_path: '/logo.png',
	favicon_path: '/favicon.ico',
	refresh_interval_ms: 5000,
	services: { magnum: false, manila: false, zun: false, k3s: false, trove: false, swift: false, barbican: false },
};

function findConfigPath(): string | null {
	const candidates = [
		process.cwd() + '/afterglow.conf',
		process.cwd() + '/../afterglow.conf',
		process.cwd() + '/config.toml',
		process.cwd() + '/../config.toml',
		'/app/afterglow.conf',
		'/app/config.toml',
		'/app/afterglow.toml',
		process.cwd() + '/afterglow.toml',
	];
	for (const p of candidates) {
		try {
			readFileSync(p);
			return p;
		} catch {
			// try next
		}
	}
	return null;
}

let _cached: PublicSiteConfig | null = null;

export function loadPublicSiteConfig(): PublicSiteConfig {
	if (_cached) return _cached;

	const configPath = findConfigPath();
	if (!configPath) {
		_cached = { ...DEFAULTS, services: { ...DEFAULTS.services } };
		return _cached;
	}

	try {
		const raw = readFileSync(configPath, 'utf-8');
		const toml = parse(raw) as Record<string, unknown>;

		const app = (toml.app ?? {}) as Record<string, unknown>;
		const services = (toml.services ?? {}) as Record<string, unknown>;

		_cached = {
			site_name: String(app.site_name ?? DEFAULTS.site_name),
			site_description: String(app.site_description ?? DEFAULTS.site_description),
			logo_path: String(app.logo_path ?? DEFAULTS.logo_path),
			favicon_path: String(app.favicon_path ?? DEFAULTS.favicon_path),
			refresh_interval_ms: Number(app.refresh_interval_ms ?? DEFAULTS.refresh_interval_ms),
			services: {
				magnum: Boolean(services.magnum ?? false),
				manila: Boolean(services.manila ?? false),
				zun: Boolean(services.zun ?? false),
				k3s: Boolean(services.k3s ?? false),
				trove: Boolean(services.trove ?? false),
				swift: Boolean(services.swift ?? false),
				barbican: Boolean(services.barbican ?? false),
			},
		};
	} catch {
		_cached = { ...DEFAULTS, services: { ...DEFAULTS.services } };
	}

	return _cached;
}
