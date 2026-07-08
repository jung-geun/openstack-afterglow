import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const repoRoot = resolve(__dirname, '../../..');
const readSource = (path: string) => readFileSync(resolve(repoRoot, path), 'utf8');

const layoutSource = readSource('src/routes/+layout.svelte');
const selectProjectSource = readSource('src/routes/select-project/+page.svelte');
const loginSource = readSource('src/routes/+page.svelte');

describe('logout flow source contracts', () => {
	it('keeps confirmed logout redirect and success toast in both logged-in exit points', () => {
		for (const source of [layoutSource, selectProjectSource]) {
			expect(source).toContain("confirmDialog('로그아웃하시겠습니까?')");
			expect(source).toContain("goto('/', { replaceState: true })");
			expect(source).toContain("toast.success('정상적으로 로그아웃 되었습니다.')");
		}
	});

	it('keeps logout completion UI out of the login page source', () => {
		expect(loginSource).not.toContain('logged_out');
		expect(loginSource).not.toContain('<Alert tone="success">로그아웃되었습니다.</Alert>');
	});


	it('keeps the layout logout guard suppressed during redirect and renders toast outside the logged-in confirm block', () => {
		expect(layoutSource).toContain('if (!$logoutInProgress && !$isLoggedIn');

		const loggedInBlockStart = layoutSource.indexOf('{#if $isLoggedIn}');
		const confirmDialogIndex = layoutSource.indexOf('<ConfirmDialog />');
		const loggedInBlockEnd = layoutSource.indexOf('{/if}', confirmDialogIndex);
		const toastIndex = layoutSource.indexOf('<Toast />');

		expect(loggedInBlockStart).toBeGreaterThan(-1);
		expect(confirmDialogIndex).toBeGreaterThan(loggedInBlockStart);
		expect(loggedInBlockEnd).toBeGreaterThan(confirmDialogIndex);
		expect(toastIndex).toBeGreaterThan(loggedInBlockEnd);
	});
});
