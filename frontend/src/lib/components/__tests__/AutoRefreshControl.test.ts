import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import AutoRefreshControlWrapper from './_AutoRefreshControlWrapper.svelte';

describe('AutoRefreshControl', () => {
	it('초기 active=false 시 "자동 새로고침 켜기" title 표시', () => {
		render(AutoRefreshControlWrapper, { active: false });
		flushSync();
		const btn = screen.getByTitle('자동 새로고침 켜기');
		expect(btn).toBeTruthy();
	});

	it('초기 active=true 시 "자동 새로고침 끄기" title 표시', () => {
		render(AutoRefreshControlWrapper, { active: true });
		flushSync();
		const btn = screen.getByTitle('자동 새로고침 끄기');
		expect(btn).toBeTruthy();
	});

	it('토글 버튼 클릭 시 active 상태 변경', async () => {
		render(AutoRefreshControlWrapper, { active: false });
		flushSync();
		const btn = screen.getByTitle('자동 새로고침 켜기');
		await fireEvent.click(btn);
		flushSync();
		expect(screen.getByTestId('active-state').textContent).toBe('true');
	});

	it('intervalOptions가 select에 렌더링', () => {
		render(AutoRefreshControlWrapper, { intervalOptions: [5, 10, 20] });
		flushSync();
		const select = screen.getByTitle('새로고침 주기') as HTMLSelectElement;
		const options = Array.from(select.options).map((o) => o.text);
		expect(options).toContain('5s');
		expect(options).toContain('10s');
		expect(options).toContain('20s');
	});

	it('refreshing=false 시 "새로고침" 버튼 표시', () => {
		const onRefresh = vi.fn();
		render(AutoRefreshControlWrapper, { refreshing: false, onManualRefresh: onRefresh });
		flushSync();
		expect(screen.getByText('새로고침')).toBeTruthy();
	});

	it('refreshing=true 시 "로딩 중…" 버튼 표시 및 disabled', () => {
		render(AutoRefreshControlWrapper, { refreshing: true, onManualRefresh: vi.fn() });
		flushSync();
		const btn = screen.getByText('로딩 중…') as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
	});

	it('새로고침 버튼 클릭 시 onManualRefresh 호출', async () => {
		const onRefresh = vi.fn();
		render(AutoRefreshControlWrapper, { onManualRefresh: onRefresh });
		flushSync();
		await fireEvent.click(screen.getByText('새로고침'));
		expect(onRefresh).toHaveBeenCalledOnce();
	});
});
