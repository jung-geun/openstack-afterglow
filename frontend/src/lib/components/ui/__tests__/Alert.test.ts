import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import Alert from '../Alert.svelte';

const textSnippet = (text: string) => createRawSnippet(() => ({ render: () => text }));

describe('Alert', () => {
	it('renders child text', () => {
		render(Alert, { children: textSnippet('Something happened') });
		expect(screen.getByText('Something happened')).toBeTruthy();
	});

	it('renders optional title', () => {
		render(Alert, { title: 'Heads up', children: textSnippet('Details') });
		expect(screen.getByText('Heads up')).toBeTruthy();
	});

	it('defaults to danger tone', () => {
		const { container } = render(Alert, { children: textSnippet('Danger') });
		expect(container.querySelector('.alert-danger')).toBeTruthy();
	});

	it('applies success tone', () => {
		const { container } = render(Alert, { tone: 'success', children: textSnippet('Saved') });
		expect(container.querySelector('.alert-success')).toBeTruthy();
	});

	it('renders action snippets', () => {
		render(Alert, { children: textSnippet('Needs action'), actions: textSnippet('<button>Retry</button>') });
		expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
	});
});
