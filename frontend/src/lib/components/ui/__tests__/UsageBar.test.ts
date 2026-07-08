import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import UsageBar from '../UsageBar.svelte';

describe('UsageBar', () => {
	it('maps default thresholds to accent, warning, and danger', () => {
		expect(render(UsageBar, { percent: 79 }).container.querySelector('.usage-fill-accent')).toBeTruthy();
		expect(render(UsageBar, { percent: 80 }).container.querySelector('.usage-fill-warning')).toBeTruthy();
		expect(render(UsageBar, { percent: 95 }).container.querySelector('.usage-fill-danger')).toBeTruthy();
	});

	it('uses custom thresholds', () => {
		expect(render(UsageBar, { percent: 69, thresholds: { warning: 70, danger: 90 } }).container.querySelector('.usage-fill-accent')).toBeTruthy();
		expect(render(UsageBar, { percent: 70, thresholds: { warning: 70, danger: 90 } }).container.querySelector('.usage-fill-warning')).toBeTruthy();
		expect(render(UsageBar, { percent: 90, thresholds: { warning: 70, danger: 90 } }).container.querySelector('.usage-fill-danger')).toBeTruthy();
	});
});
