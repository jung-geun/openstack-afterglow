import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const repoRoot = resolve(__dirname, '../../..');
const readSource = (path: string) => readFileSync(resolve(repoRoot, path), 'utf8');

const layoutSource = readSource('src/routes/+layout.svelte');
const sidebarSource = readSource('src/lib/components/Sidebar.svelte');
const adminSidebarSource = readSource('src/lib/components/AdminSidebar.svelte');

describe('responsive shell control source contracts', () => {
	it('keeps the project selector in the desktop header on admin routes', () => {
		const headerControls = layoutSource.slice(
			layoutSource.indexOf('<!-- 우측 컨트롤 -->'),
			layoutSource.indexOf('<!-- 테마 토글 -->'),
		);

		expect(headerControls).toContain('<div class="hidden lg:block"><ProjectSelector direction="down" /></div>');
		expect(headerControls).not.toContain("!$page.url.pathname.startsWith('/admin')");
	});

	it('keeps dashboard sidebar footer controls pinned below a scrollable menu', () => {
		expect(sidebarSource).toContain('flex flex-col overflow-y-auto');
		expect(sidebarSource).toContain('<nav class="flex-1 min-h-0 overflow-y-auto');
		expect(sidebarSource).toContain('<div class="p-3 lg:hidden">');
		expect(sidebarSource).toContain('<div class="px-3 pb-3 lg:hidden">');
	});

	it('keeps administrator sidebar controls on the same desktop breakpoint', () => {
		expect(adminSidebarSource).toContain('flex flex-col overflow-y-auto');
		expect(adminSidebarSource).toContain('<nav class="flex-1 min-h-0 overflow-y-auto');
		expect(adminSidebarSource).toContain('<div class="p-3 lg:hidden">');
		expect(adminSidebarSource).toContain('<div class="p-3 pt-0 lg:hidden">');
	});
});
