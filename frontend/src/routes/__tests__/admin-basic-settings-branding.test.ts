import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import SettingsPage from '../admin/settings/+page.svelte';

const root = resolve(__dirname, '../../..');
const readSource = (path: string) => readFileSync(resolve(root, path), 'utf8');

const kubernetesHeptagonPath = 'M12 2.4 19.8 6.1 21.7 14.3 16.3 20.8H7.7l-5.4-6.5 1.9-8.2L12 2.4Z';
const legacyShieldPath = 'M12 2l8 4v6c0 5.55 3.84 10.74 8 12';
const legacyClusterCardShieldPath = 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z';

describe('admin basic settings and Drover branding source contracts', () => {
	it('compiles the dedicated admin settings page component', () => {
		expect(SettingsPage).toBeTruthy();
	});

	it('keeps login branding on the dedicated admin settings page', () => {
		const overviewSource = readSource('src/routes/admin/+page.svelte');
		const settingsSource = readSource('src/routes/admin/settings/+page.svelte');
		const sidebarSource = readSource('src/lib/components/AdminSidebar.svelte');
		const navSource = readSource('src/lib/config/nav.ts');

		expect(overviewSource).not.toContain('AdminLoginBrandingPanel');
		expect(settingsSource).toContain('AdminLoginBrandingPanel');
		expect(settingsSource).toContain('title="기본 설정"');
		expect(sidebarSource).toContain("{ label: '기본 설정', href: '/admin/settings', service: null }");
		expect(navSource).toContain("{ label: '기본 설정', href: '/admin/settings', service: null }");
	});

	it('uses the Kubernetes mark for Drover cluster surfaces', () => {
		const dashboardTileSource = readSource('src/lib/components/dashboard/overview/DashboardStatTiles.svelte');
		const clusterCardSource = readSource('src/lib/components/dashboard/drover/K3sClusterCard.svelte');

		expect(dashboardTileSource).toContain(kubernetesHeptagonPath);
		expect(clusterCardSource).toContain(kubernetesHeptagonPath);
		expect(dashboardTileSource).not.toContain(legacyShieldPath);
		expect(clusterCardSource).not.toContain(legacyClusterCardShieldPath);
	});
});
