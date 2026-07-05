import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const loginSource = readFileSync(resolve(__dirname, '../+page.svelte'), 'utf8');
const callbackSource = readFileSync(resolve(__dirname, '../auth/gitlab/callback/+page.svelte'), 'utf8');

describe('GitLab auth route/API path contract', () => {
	it('keeps browser page routes public while calling the v1 backend API', () => {
		expect(loginSource).toContain("api.get<{ enabled: boolean }>('/api/v1/auth/gitlab/enabled')");
		expect(loginSource).toContain("api.get<{ authorize_url: string }>('/api/v1/auth/gitlab/authorize')");
		expect(callbackSource).toContain("history.replaceState(null, '', '/auth/gitlab/callback')");
		expect(callbackSource).toContain("}>('/api/v1/auth/gitlab/callback', { code, state })");
	});

	it('does not call the UI callback route as a backend API endpoint', () => {
		expect(loginSource).not.toMatch(/api\.(?:get|post)<[^>]*>\('\/auth\/gitlab\//);
		expect(callbackSource).not.toMatch(/api\.(?:get|post)<[^>]*>\('\/auth\/gitlab\//);
	});
});
