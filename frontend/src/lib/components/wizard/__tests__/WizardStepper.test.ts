import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import WizardStepper from '../WizardStepper.svelte';

describe('WizardStepper', () => {
	it('exposes a compact progress bar alongside the full stepper', () => {
		const { container } = render(WizardStepper, {
			cur: 2,
			totalSteps: 4,
			stepLabels: ['이미지', '플레이버', '라이브러리', '검토'],
			goTo: vi.fn(),
		});

		const full = container.querySelector('.full-stepper');
		expect(full?.className).toContain('max-[479px]:hidden');
		expect(full).toBeTruthy();
		const compact = screen.getByRole('progressbar', { name: 'VM 생성 진행률' });
		expect(compact.className).toContain('hidden');
		expect(compact.className).toContain('max-[479px]:block');
		expect(compact.getAttribute('aria-valuenow')).toBe('2');
		expect(compact.getAttribute('aria-valuemax')).toBe('4');
		expect(compact.querySelector('.compact-progress-fill')?.getAttribute('style')).toContain('50%');
	});
});
