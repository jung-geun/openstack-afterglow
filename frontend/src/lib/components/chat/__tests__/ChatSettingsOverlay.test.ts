import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ChatSettingsOverlay from '../ChatSettingsOverlay.svelte';

describe('ChatSettingsOverlay', () => {
	it('opens on usage and leaves theme controls to the global header', () => {
		render(ChatSettingsOverlay, { open: true, onClose: () => {}, usage: null });

		expect(screen.getByRole('button', { name: '사용량' })).toBeTruthy();
		expect(screen.getByRole('heading', { name: '이번 달 사용량' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: '라이트' })).toBeNull();
		expect(screen.queryByRole('button', { name: '다크' })).toBeNull();
		expect(screen.queryByRole('button', { name: '시스템' })).toBeNull();
	});
});
