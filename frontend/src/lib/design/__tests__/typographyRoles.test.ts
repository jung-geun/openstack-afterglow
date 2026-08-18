import { existsSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const repoRoot = resolve(__dirname, '../../../../..');
const frontendRoot = resolve(repoRoot, 'frontend');
const layoutSource = readFileSync(resolve(frontendRoot, 'src/routes/layout.css'), 'utf8');
const tokenSource = readFileSync(resolve(frontendRoot, 'src/lib/design/tokens.ts'), 'utf8');
const landingSource = readFileSync(resolve(frontendRoot, 'src/lib/components/landing/LandingPage.svelte'), 'utf8');
const opsBoardSource = readFileSync(resolve(frontendRoot, 'src/lib/components/landing/LandingOpsBoard.svelte'), 'utf8');
const designSource = readFileSync(resolve(repoRoot, 'DESIGN.md'), 'utf8');

const fontFiles = [
	'pretendard/PretendardVariable.woff2',
	'ibm-plex/IBMPlexSansKR-Medium.woff2',
	'ibm-plex/IBMPlexSansKR-SemiBold.woff2',
	'ibm-plex/IBMPlexMono-Regular.woff2',
	'ibm-plex/IBMPlexMono-Medium.woff2',
];

describe('role-based typography system', () => {
	it('bundles the selected open-licensed WOFF2 files within the intended payload', () => {
		const fontRoot = resolve(frontendRoot, 'static/fonts');
		const totalBytes = fontFiles.reduce((total, file) => {
			const path = resolve(fontRoot, file);
			expect(existsSync(path)).toBe(true);
			return total + statSync(path).size;
		}, 0);

		expect(totalBytes).toBeLessThan(3_500_000);
		expect(existsSync(resolve(fontRoot, 'pretendard/LICENSE.txt'))).toBe(true);
		expect(existsSync(resolve(fontRoot, 'ibm-plex/LICENSE.txt'))).toBe(true);
	});

	it('defines sans, display, and mono roles in the authoritative CSS and TypeScript tokens', () => {
		expect(layoutSource).toContain('font-family: "Pretendard Variable"');
		expect(layoutSource).toContain('font-family: "IBM Plex Sans KR"');
		expect(layoutSource).toContain('font-family: "IBM Plex Mono"');
		expect(layoutSource).toContain('--font-display: "IBM Plex Sans KR"');
		expect(layoutSource).toContain('--font-mono: "IBM Plex Mono", "Pretendard Variable"');
		expect(layoutSource.match(/font-display: swap;/g)).toHaveLength(5);
		expect(layoutSource).not.toContain('MaruBuri');
		expect(layoutSource).not.toMatch(/https?:\/\//);
		expect(tokenSource).toContain('export const FONT_CSS_VAR');
		expect(tokenSource).toContain("display: 'var(--font-display)'");
	});

	it('keeps display typography on editorial headings and documents the same role boundary', () => {
		expect(landingSource).toContain('.hero h1, .section h2, .cap-content h3, blockquote, .audience-note strong { font-family: var(--font-display); }');
		expect(landingSource).toContain('font-family: var(--font-sans);');
		expect(designSource).toContain('Typography has three explicit roles');
		expect(designSource).toContain('do not use it for ordinary console page titles or controls');
	});

	it('delays the dense one-row operations board until the xl width can preserve values', () => {
		expect(opsBoardSource).toContain('@media (min-width: 1024px)');
		expect(opsBoardSource).toContain('@media (min-width: 1280px)');
		expect(designSource).toContain('The board retains its readable two-row desktop flow until the `xl` density refinement (`≥1280px`)');
	});
});
