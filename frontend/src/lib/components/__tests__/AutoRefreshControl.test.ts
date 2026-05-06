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

	it('새로고침 주기 select가 렌더링됨', () => {
		render(AutoRefreshControlWrapper, {});
		flushSync();
		const select = screen.getByTitle('새로고침 주기');
		expect(select).toBeTruthy();
	});

	it('intervalOptions가 select에 렌더링 (Off 포함)', () => {
		render(AutoRefreshControlWrapper, { intervalOptions: [5, 10, 20] });
		flushSync();
		const select = screen.getByTitle('새로고침 주기') as HTMLSelectElement;
		const options = Array.from(select.options).map((o) => o.text);
		expect(options).toContain('Off');
		expect(options).toContain('5s');
		expect(options).toContain('10s');
		expect(options).toContain('20s');
	});

	it('select에서 Off 선택 시 active=false', async () => {
		render(AutoRefreshControlWrapper, { active: true, intervalSeconds: 30 });
		flushSync();
		const select = screen.getByTitle('새로고침 주기') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: 'off' } });
		flushSync();
		expect(screen.getByTestId('active-state').textContent).toBe('false');
	});

	it('select에서 인터벌 선택 시 active=true + intervalSeconds 갱신', async () => {
		render(AutoRefreshControlWrapper, { active: false, intervalSeconds: 30, intervalOptions: [10, 30, 60] });
		flushSync();
		const select = screen.getByTitle('새로고침 주기') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '10' } });
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
