import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import LandingOpsBoard from '../LandingOpsBoard.svelte';

describe('LandingOpsBoard', () => {
	it('renders the default research delivery flow with an accessible scenario control', () => {
		const { container } = render(LandingOpsBoard);

		expect(screen.getByRole('region', { name: '연구 환경 제공 현황' })).toBeTruthy();
		expect(screen.getByRole('group', { name: '연구 운영 시나리오' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'GPU 연구' }).getAttribute('aria-pressed')).toBe('true');
		expect(container.querySelector('.ops-board')?.getAttribute('data-scenario')).toBe('gpu');
		expect(container.textContent).toContain('멀티모달 학습 환경');
		expect(container.textContent).toContain('pytorch-vision-lab');
	});

	it('updates policy, allocation, and reusable output when the scenario changes', async () => {
		const { container } = render(LandingOpsBoard);

		await fireEvent.click(screen.getByRole('button', { name: '클러스터 실습' }));
		expect(container.querySelector('.ops-board')?.getAttribute('data-scenario')).toBe('cluster');
		expect(screen.getByRole('button', { name: '클러스터 실습' }).getAttribute('aria-pressed')).toBe('true');
		expect(container.textContent).toContain('분산 학습 실습 환경');
		expect(container.textContent).toContain('K8s 노드');
		expect(container.textContent).toContain('distributed-training');

		await fireEvent.click(screen.getByRole('button', { name: '공유 데이터' }));
		expect(container.querySelector('.ops-board')?.getAttribute('data-scenario')).toBe('data');
		expect(container.textContent).toContain('팀 데이터셋 분석 공간');
		expect(container.textContent).toContain('2 TB');
		expect(container.textContent).toContain('genomics-baseline');
	});
});
