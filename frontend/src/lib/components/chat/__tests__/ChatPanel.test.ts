import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatPanel from '../ChatPanel.svelte';

beforeEach(() => {
	vi.stubGlobal('matchMedia', () => ({
		matches: false,
		media: '',
		onchange: null,
		addEventListener: () => {},
		removeEventListener: () => {},
		addListener: () => {},
		removeListener: () => {},
		dispatchEvent: () => false
	}));
});

describe('ChatPanel', () => {
	it('renders an empty chat without a derived-state initialization error', () => {
		render(ChatPanel);

		expect(screen.getByRole('heading', { name: '무엇을 도와드릴까요?' })).toBeTruthy();
	});
});
