import { fireEvent, render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';
import LandingFigure from '../LandingFigure.svelte';

const textSnippet = (text: string) => createRawSnippet(() => ({ render: () => text }));

describe('LandingFigure', () => {
	it('renders a semantic figure with a lazy async-decoded image by default', () => {
		render(LandingFigure, { src: '/plate.svg', alt: '연구 이미지' });

		const figure = screen.getByRole('figure');
		const image = screen.getByRole('img', { name: '연구 이미지' });

		expect(figure).toBeTruthy();
		expect(image.getAttribute('src')).toBe('/plate.svg');
		expect(image.getAttribute('loading')).toBe('lazy');
		expect(image.getAttribute('decoding')).toBe('async');
	});

	it('omits loading for an eager image', () => {
		render(LandingFigure, { src: '/hero.svg', alt: '히어로 이미지', lazy: false });

		expect(screen.getByRole('img', { name: '히어로 이미지' }).getAttribute('loading')).toBeNull();
	});

	it('renders optional caption content in a figcaption', () => {
		render(LandingFigure, {
			src: '/plate.svg',
			alt: '연구 이미지',
			children: textSnippet('연구 캡션'),
		});

		const figure = screen.getByRole('figure');
		const caption = figure.querySelector('figcaption');
		expect(caption).toBeTruthy();
		expect(caption?.textContent).toBe('연구 캡션');
	});

	it('marks failed images and exposes the Korean fallback label', async () => {
		render(LandingFigure, { src: '/missing.svg', alt: '연구 이미지' });

		const figure = screen.getByRole('figure');
		const image = screen.getByRole('img', { name: '연구 이미지' });
		await fireEvent.error(image);

		expect(figure.classList.contains('is-broken')).toBe(true);
		expect(figure.getAttribute('data-fallback-label')).toBe(
			'연구 이미지 이미지를 불러오지 못했습니다.',
		);
	});
});
