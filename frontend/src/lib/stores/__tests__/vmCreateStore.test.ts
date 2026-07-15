import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_BETA_FEATURES, betaFeatures } from '../betaFeatures';
import { resetWizard, wizard } from '../wizard';
import VmCreateStoreWrapper from './_VmCreateStoreWrapper.svelte';

describe('vmCreateStore 자동 단계 진행', () => {
	beforeEach(() => {
		betaFeatures.set(DEFAULT_BETA_FEATURES);
		resetWizard();
	});

	it('이미지 선택 시 다음 visible 단계로 진행하고 이전으로 돌아올 수 있다', async () => {
		render(VmCreateStoreWrapper);

		await fireEvent.click(screen.getByTestId('select-image'));
		expect(screen.getByTestId('wizard-step').textContent).toBe('2');

		await fireEvent.click(screen.getByTestId('previous-step'));
		expect(screen.getByTestId('wizard-step').textContent).toBe('1');
	});

	it('플레이버 선택 시 다음 visible 단계로 진행', async () => {
		wizard.update((w) => ({ ...w, step: 2 }));
		render(VmCreateStoreWrapper);

		await fireEvent.click(screen.getByTestId('select-flavor'));
		expect(screen.getByTestId('wizard-step').textContent).toBe('5');
	});
});
