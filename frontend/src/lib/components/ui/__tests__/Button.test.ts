import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import Button from '../Button.svelte';

const textSnippet = (text: string) => createRawSnippet(() => ({ render: () => text }));

describe('Button', () => {
	it('renders a native button by default', () => {
		render(Button, { children: textSnippet('Save') });
		expect(screen.getByRole('button', { name: 'Save' })).toBeTruthy();
	});

	it('renders an anchor when href is supplied', () => {
		render(Button, { href: '/x', children: textSnippet('Open') });
		const link = screen.getByRole('link', { name: 'Open' });
		expect(link.getAttribute('href')).toBe('/x');
	});

	it('applies the accent variant class', () => {
		render(Button, { variant: 'accent', children: textSnippet('Run') });
		expect(screen.getByRole('button', { name: 'Run' }).classList.contains('btn-accent')).toBe(true);
	});

	it('applies the xs size class', () => {
		render(Button, { size: 'xs', children: textSnippet('Tiny') });
		expect(screen.getByRole('button', { name: 'Tiny' }).classList.contains('btn-xs')).toBe(true);
	});

	it('disables native buttons', () => {
		render(Button, { disabled: true, children: textSnippet('Disabled') });
		expect((screen.getByRole('button', { name: 'Disabled' }) as HTMLButtonElement).disabled).toBe(true);
	});

	it('calls onclick once for enabled click', async () => {
		const onclick = vi.fn();
		render(Button, { onclick, children: textSnippet('Click') });
		await fireEvent.click(screen.getByRole('button', { name: 'Click' }));
		expect(onclick).toHaveBeenCalledTimes(1);
	});
});
