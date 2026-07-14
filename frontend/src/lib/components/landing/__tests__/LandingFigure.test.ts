import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';
import LandingFigure from '../LandingFigure.svelte';

const textSnippet = (text: string) => createRawSnippet(() => ({ render: () => text }));

describe('LandingFigure', () => {
	it('renders a semantic figure wrapping a theme-aware inline plate graphic', () => {
		const { container } = render(LandingFigure, { name: 'kubernetes', alt: '연구 이미지' });

		const figure = screen.getByRole('figure');
		const graphic = container.querySelector('svg.plate-graphic');

		expect(figure).toBeTruthy();
		expect(graphic).toBeTruthy();
		expect(graphic?.getAttribute('data-plate')).toBe('kubernetes');
		expect(graphic?.getAttribute('role')).toBe('img');
		expect(graphic?.getAttribute('aria-label')).toBe('연구 이미지');
	});

	it('defaults to a contain fit and honors an explicit cover fit', () => {
		const { container: contain } = render(LandingFigure, { name: 'console', alt: '기본' });
		expect(contain.querySelector('svg.plate-graphic')?.getAttribute('preserveAspectRatio')).toBe(
			'xMidYMid meet',
		);

		const { container: cover } = render(LandingFigure, {
			name: 'console',
			alt: '커버',
			fit: 'cover',
		});
		expect(cover.querySelector('svg.plate-graphic')?.getAttribute('preserveAspectRatio')).toBe(
			'xMidYMid slice',
		);
	});

	it('renders optional caption content in a figcaption', () => {
		render(LandingFigure, {
			name: 'quota',
			alt: '연구 이미지',
			children: textSnippet('연구 캡션'),
		});

		const figure = screen.getByRole('figure');
		const caption = figure.querySelector('figcaption');
		expect(caption).toBeTruthy();
		expect(caption?.textContent).toBe('연구 캡션');
	});
});
