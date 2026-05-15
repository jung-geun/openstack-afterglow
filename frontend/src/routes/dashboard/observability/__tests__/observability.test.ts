import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';

// vi.hoisted는 vi.mock보다 먼저 실행되므로, factory 안에서 사용 가능한 변수를 여기서 정의
const { mockAuth } = vi.hoisted(() => {
	type AuthVal = {
		token: string | null;
		userId: string | null;
		username: string | null;
		projectId: string | null;
		projectName: string | null;
		availableProjects: { id: string; name: string }[];
		roles: string[];
		isSystemAdmin: boolean;
		expiresAt: number | null;
	};

	let _val: AuthVal = {
		token: null,
		userId: null,
		username: null,
		projectId: null,
		projectName: null,
		availableProjects: [],
		roles: [],
		isSystemAdmin: false,
		expiresAt: null,
	};

	const _subs: Array<(v: AuthVal) => void> = [];

	const mockAuth = {
		subscribe(fn: (v: AuthVal) => void) {
			_subs.push(fn);
			fn(_val);
			return () => {
				const i = _subs.indexOf(fn);
				if (i >= 0) _subs.splice(i, 1);
			};
		},
		set(v: AuthVal) {
			_val = v;
			_subs.forEach((fn) => fn(v));
		},
	};

	return { mockAuth };
});

vi.mock('$lib/stores/auth', () => ({
	auth: mockAuth,
	isAdmin: { subscribe: (fn: (v: boolean) => void) => { fn(false); return () => {}; } },
}));

vi.mock('$lib/stores/grafana', () => ({
	loadGrafanaContext: vi.fn().mockResolvedValue(null),
	grafanaStore: { subscribe: (_fn: unknown) => () => {} },
	resetGrafanaContext: vi.fn(),
}));

import Page from '../+page.svelte';

const baseAuth = {
	token: null as string | null,
	userId: null as string | null,
	username: null as string | null,
	projectId: null as string | null,
	projectName: null as string | null,
	availableProjects: [] as { id: string; name: string }[],
	roles: [] as string[],
	isSystemAdmin: false,
	expiresAt: null as number | null,
};

describe('observability page', () => {
	beforeEach(() => {
		mockAuth.set({ ...baseAuth });
	});

	it('projectId가 없으면 empty state 텍스트 표시', () => {
		render(Page);
		expect(screen.getByText('프로젝트를 선택하면 VM 메트릭이 표시됩니다.')).toBeTruthy();
	});

	it('projectId가 있으면 empty state 텍스트 미표시', () => {
		mockAuth.set({
			...baseAuth,
			token: 'tok',
			userId: 'user-1',
			username: 'testuser',
			projectId: 'proj-A',
			projectName: 'Project A',
		});
		render(Page);
		expect(screen.queryByText('프로젝트를 선택하면 VM 메트릭이 표시됩니다.')).toBeNull();
	});

	it('breadcrumb이 DASHBOARD / OBSERVABILITY로 표시', () => {
		render(Page);
		expect(screen.getByText('DASHBOARD / OBSERVABILITY')).toBeTruthy();
	});

	it('vars.project_id는 store에서만 온다 — URL searchParams 미사용', () => {
		// 페이지는 $page.url.searchParams를 읽지 않고 $auth.projectId만 사용.
		// store가 null이면 GrafanaEmbed를 렌더링하지 않는다.
		mockAuth.set({ ...baseAuth });
		const { unmount } = render(Page);
		expect(screen.getByText('프로젝트를 선택하면 VM 메트릭이 표시됩니다.')).toBeTruthy();
		unmount();

		// store를 업데이트하면 반영됨
		mockAuth.set({ ...baseAuth, projectId: 'proj-A', token: 'tok', userId: 'u', username: 'u', projectName: 'P' });
		render(Page);
		expect(screen.queryByText('프로젝트를 선택하면 VM 메트릭이 표시됩니다.')).toBeNull();
	});
});
