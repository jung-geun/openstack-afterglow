import { describe, expect, it } from 'vitest';

import { deriveBrowserApiBase } from './config';

describe('deriveBrowserApiBase', () => {
	it('prefers explicit public_api_base over frontend_base_url', () => {
		expect(
			deriveBrowserApiBase(
				{
					public_api_base: 'https://api.example.com/root/path',
					frontend_base_url: 'https://frontend.example.com/app',
					backend_port: 9000,
				},
				{},
			),
		).toBe('https://api.example.com');
	});

	it('lets PUBLIC_API_BASE override afterglow.conf for docker compose', () => {
		expect(
			deriveBrowserApiBase(
				{
					public_api_base: 'https://cloud.dmslab.re.kr',
					frontend_base_url: 'https://cloud.dmslab.re.kr',
					backend_port: 8000,
				},
				{ PUBLIC_API_BASE: 'http://localhost:8000' },
			),
		).toBe('http://localhost:8000');
	});

	it('falls back to frontend_base_url when public_api_base is empty or invalid', () => {
		expect(
			deriveBrowserApiBase(
				{
					public_api_base: 'not a url',
					frontend_base_url: 'https://afterglow.example.com/app',
					backend_port: 9000,
				},
				{},
			),
		).toBe('https://afterglow.example.com');
	});

	it('uses backend_port for local development when no public origin is configured', () => {
		expect(deriveBrowserApiBase({ backend_port: 8123 }, {})).toBe('http://localhost:8123');
	});
});
