import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import SlidePanelWrapper from './_SlidePanelWrapper.svelte';

// jsdom은 Web Animations API / matchMedia를 지원하지 않음 — mock 필요
beforeEach(() => {
	Element.prototype.animate = vi.fn().mockReturnValue({
		finished: Promise.resolve(),
		cancel: vi.fn(),
		play: vi.fn(),
	});
	window.matchMedia = vi.fn().mockImplementation((query: string) => ({
		matches: false,
		media: query,
		onchange: null,
		addListener: vi.fn(),
		removeListener: vi.fn(),
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		dispatchEvent: vi.fn(),
	}));
});

describe('SlidePanel', () => {
	it('role=dialog aria-modal=true로 렌더링', () => {
		render(SlidePanelWrapper, { onClose: vi.fn() });
		flushSync();
		const dialog = screen.getByRole('dialog');
		expect(dialog.getAttribute('aria-modal')).toBe('true');
	});

	it('children이 렌더링됨', () => {
		render(SlidePanelWrapper, { onClose: vi.fn(), content: '패널 내용' });
		flushSync();
		expect(screen.getByText('패널 내용')).toBeTruthy();
	});

	it('backdrop 버튼이 "패널 닫기" aria-label을 가짐', () => {
		render(SlidePanelWrapper, { onClose: vi.fn() });
		flushSync();
		const closeBtn = screen.getByLabelText('패널 닫기');
		expect(closeBtn).toBeTruthy();
	});

	it('backdrop 클릭 시 onClose 호출', async () => {
		const onClose = vi.fn();
		render(SlidePanelWrapper, { onClose });
		flushSync();
		const closeBtn = screen.getByLabelText('패널 닫기');
		await fireEvent.click(closeBtn);
		expect(onClose).toHaveBeenCalledOnce();
	});

	it('Escape 키 누를 시 onClose 호출', async () => {
		const onClose = vi.fn();
		render(SlidePanelWrapper, { onClose });
		flushSync();
		const dialog = screen.getByRole('dialog');
		await fireEvent.keyDown(dialog, { key: 'Escape' });
		expect(onClose).toHaveBeenCalledOnce();
	});
});
