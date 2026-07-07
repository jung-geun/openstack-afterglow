import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import AutoRefreshControlWrapper from './_AutoRefreshControlWrapper.svelte';

describe('AutoRefreshControl', () => {
	it('새로고침 버튼이 렌더링됨', () => {
		render(AutoRefreshControlWrapper, { active: false });
		flushSync();
		const btn = screen.getByTitle('지금 새로고침');
		expect(btn).toBeTruthy();
	});

	it('새로고침 주기 toggle group이 렌더링됨', () => {
		render(AutoRefreshControlWrapper, {});
		flushSync();
		const group = screen.getByRole('group');
		expect(group).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Off' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '10s' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '30s' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '60s' })).toBeTruthy();
	});

	it('intervalOptions가 toggle group에 렌더링 (Off 포함)', () => {
		render(AutoRefreshControlWrapper, { intervalOptions: [5, 10, 20] });
		flushSync();
		expect(screen.getByRole('button', { name: 'Off' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '5s' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '10s' })).toBeTruthy();
		expect(screen.getByRole('button', { name: '20s' })).toBeTruthy();
	});

	it('toggle에서 Off 선택 시 active=false', async () => {
		render(AutoRefreshControlWrapper, { active: true, intervalSeconds: 30 });
		flushSync();
		await fireEvent.click(screen.getByRole('button', { name: 'Off' }));
		flushSync();
		expect(screen.getByTestId('active-state').textContent).toBe('false');
	});

	it('toggle에서 인터벌 선택 시 active=true + intervalSeconds 갱신', async () => {
		render(AutoRefreshControlWrapper, { active: false, intervalSeconds: 30, intervalOptions: [10, 30, 60] });
		flushSync();
		await fireEvent.click(screen.getByRole('button', { name: '10s' }));
		flushSync();
		expect(screen.getByTestId('active-state').textContent).toBe('true');
		expect(screen.getByTestId('interval-state').textContent).toBe('10');
	});

	it('refreshing=false 시 버튼 enabled', () => {
		const onRefresh = vi.fn();
		render(AutoRefreshControlWrapper, { refreshing: false, onManualRefresh: onRefresh });
		flushSync();
		const btn = screen.getByTitle('지금 새로고침') as HTMLButtonElement;
		expect(btn.disabled).toBe(false);
	});

	it('refreshing=true 시 버튼 disabled', () => {
		render(AutoRefreshControlWrapper, { refreshing: true, onManualRefresh: vi.fn() });
		flushSync();
		const btn = screen.getByTitle('로딩 중…') as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
	});

	it('새로고침 버튼 클릭 시 onManualRefresh 호출', async () => {
		const onRefresh = vi.fn();
		render(AutoRefreshControlWrapper, { onManualRefresh: onRefresh });
		flushSync();
		await fireEvent.click(screen.getByTitle('지금 새로고침'));
		expect(onRefresh).toHaveBeenCalledOnce();
	});
});
