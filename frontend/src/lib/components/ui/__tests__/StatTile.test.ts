import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import LinkedStatTileFixture from './StatTileLinkedFixture.svelte';

const componentSource = readFileSync(resolve(__dirname, '../StatTile.svelte'), 'utf8');
const styleSource = componentSource.match(/<style>([\s\S]*?)<\/style>/)?.[1] ?? '';

const normalizeCss = (source: string) => source.replace(/\s+/g, ' ').trim();

describe('StatTile', () => {
	it('only applies clickable hover/focus treatment when the tile is inside an anchor', () => {
		const css = normalizeCss(styleSource);

		expect(css).toMatch(/:global\(a:hover\)\s*>\s*\.stat-tile,\s*:global\(a:focus-visible\)\s*>\s*\.stat-tile\s*\{/);
		expect(css).toContain('border-color: var(--stat-tile-ring)');
		expect(css).toContain('background: color-mix(in oklab, var(--stat-tile-tone)');
		expect(css).toContain('box-shadow: 0 10px 28px color-mix(in oklab, var(--stat-tile-tone)');
		expect(css).toContain('transform: translateY(-1px)');
		expect(css).not.toContain('.stat-tile:hover');
		expect(css).not.toContain('.stat-tile:focus-visible');
	});

	it('keeps the tone class on a linked stat tile direct child', () => {
		const { container } = render(LinkedStatTileFixture);

		const linkedTile = container.querySelector('a[href="/admin/users"] > .stat-tile.tile-warning');
		expect(linkedTile).toBeTruthy();
		expect(linkedTile?.textContent).toContain('사용자');
		expect(linkedTile?.textContent).toContain('4');
		expect(linkedTile?.textContent).toContain('명');
	});
});
