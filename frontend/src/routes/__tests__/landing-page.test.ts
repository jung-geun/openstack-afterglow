import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = resolve(__dirname, '../../..');
const readSource = (path: string) => readFileSync(resolve(root, path), 'utf8');

const landingRouteSource = readSource('src/routes/+page.svelte');
const landingComponentSource = readSource('src/lib/components/landing/LandingPage.svelte');
const landingSource = `${landingRouteSource}\n${landingComponentSource}`;
const loginRouteSource = readSource('src/routes/login/+page.svelte');
const loginComponentSource = readSource('src/lib/components/auth/LoginPage.svelte');
const loginSource = `${loginRouteSource}\n${loginComponentSource}`;
const appHtmlSource = readSource('src/app.html');
const layoutSource = readSource('src/routes/+layout.svelte');
const clientSource = readSource('src/lib/api/client.ts');
const hooksSource = readSource('src/hooks.server.ts');
const callbackSource = readSource('src/routes/auth/gitlab/callback/+page.svelte');
const layoutCssSource = readSource('src/routes/layout.css');

const rawPaletteClassPattern = /\b(?:bg|text|border)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}/;

describe('public landing and login route source contracts', () => {
	it('keeps the root adapter wired to the Open Design landing with auth-aware console CTA', () => {
		expect(landingRouteSource).toContain(
			"const consoleHref = $derived($page.data.mockup?.active ? $page.data.mockup.homePath : ($isLoggedIn ? ($auth.projectId ? '/dashboard' : '/select-project') : '/login'));",
		);
		expect(landingRouteSource).toContain("import { resolveLandingLogoPath } from '$lib/config/brandAssets';");
		expect(landingRouteSource).toContain("import { resolvedTheme } from '$lib/stores/theme';");
		expect(landingRouteSource).toContain("import { onMount } from 'svelte';");
		expect(landingRouteSource).toContain('let themeReady = $state(false);');
		expect(landingRouteSource).toContain('themeReady = true;');
		expect(landingRouteSource).toContain("const landingLogoPath = $derived(resolveLandingLogoPath($siteConfig, themeReady ? $resolvedTheme : 'dark'));");
		expect(landingRouteSource.replace(/\s+/g, ' ')).toContain(
			'<LandingPage siteName={$siteConfig.site_name} logoPath={landingLogoPath} {consoleHref} />',
		);
		expect(landingRouteSource).toContain('<title>{$siteConfig.site_name} | 연구실 클라우드 제공 콘솔</title>');
		expect(landingRouteSource).toContain(
			'content={`${$siteConfig.site_name}는 연구실과 교육 조직이 컴퓨팅 자원, Kubernetes, 공유 스토리지, AI/ML 라이브러리 레이어를 한 화면에서 제공하고 운영하도록 돕는 클라우드 포털입니다.`}',
		);
		expect(appHtmlSource).toContain('<html lang="ko">');
		expect(landingRouteSource).not.toContain('og:');
		expect(landingRouteSource).not.toMatch(
			/<link\b[^>]*rel\s*=\s*["'][^"']*(?:icon|shortcut icon)[^"']*["']/i,
		);
		expect(layoutSource).toContain("import { resolveFaviconPath } from '$lib/config/brandAssets';");
		expect(layoutSource).toContain("const effectiveBrandTheme = $derived(themeReady ? $resolvedTheme : 'dark');");
		expect(layoutSource).toContain('const themedFaviconPath = $derived(resolveFaviconPath($siteConfig, effectiveBrandTheme));');
		expect(layoutSource).toContain("<svelte:head><link rel=\"icon\" href={themedFaviconPath} /></svelte:head>");
		expect(layoutSource).toContain("document.documentElement.classList.toggle('light', themeReady && $resolvedTheme === 'light');");

		for (const copy of [
			'본문으로 건너뛰기',
			'개요',
			'제공 기능',
			'워크플로우',
			'화면',
			'문의',
			'콘솔 접속',
			'기능 보기',
			'연구실 클라우드를 더 쉽게 제공하는',
			'GPU 가속 VM에 필요한 GPU, vCPU, 메모리, 스토리지를 프로젝트 쿼터 안에서 배정해 개별 실험 환경을 바로 준비합니다.',
			'K8s 클러스터 노드를 구성한 뒤 수업·연구 프로젝트의 Pod와 워크로드를 배포하고 상태를 콘솔에서 추적합니다.',
			'AI/ML 라이브러리 레이어',
			'교수자와 관리자용 운영 제어',
			'컴퓨팅 자원 신청',
			'공유 데이터 공간',
			'클러스터 실습',
			'관측 가능한 운영',
			'보안과 감사',
			'연구실 클라우드 제공 방식을 정리할 준비가 되셨나요?',
			'© 2026 {siteName}. 연구 클라우드 운영 콘솔.',
		]) {
			expect(landingSource).toContain(copy);
		}
		expect(landingSource).not.toMatch(/\bk3s\b/i);
	});

	it('keeps the fixed header, active navigation, and accessible landing hooks stable', () => {
		for (const hook of [
			'<header class="top-strip">',
			'href="#landing-content"',
			'onclick={focusLandingContent}',
			"document.getElementById('landing-content')?.focus();",
			'<div id="landing-content" tabindex="-1">',
			'id="workflow-progress"',
			'ariaLabel="워크플로우 필터"',
			'onchange={selectFilter}',
			'href={`mailto:${email}`}',
			'ariaLabel="이메일 문의 보내기"',
			'class:is-active={activeSection === link.href.slice(1)}',
			"aria-current={activeSection === link.href.slice(1) ? 'location' : undefined}",
		]) {
			expect(landingComponentSource).toContain(hook);
		}
		expect(landingComponentSource).toMatch(/\.landing-page \.top-strip\s*\{\s*position:\s*fixed;/);
	});

	it('keeps login-only APIs out of the root landing route', () => {
		for (const forbidden of [
			'LoginForm',
			'LoginBrandHeader',
			"api.post<LoginResponse>('/api/v1/auth/login'",
			"api.get<{ enabled: boolean }>('/api/v1/auth/gitlab/enabled')",
		]) {
			expect(landingSource).not.toContain(forbidden);
		}
	});

	it('keeps the login API flow on /login without new raw palette classes', () => {
		expect(loginSource).toContain("api.post<LoginResponse>('/api/v1/auth/login'");
		expect(loginSource).toContain("api.get<{ enabled: boolean }>('/api/v1/auth/gitlab/enabled')");
		expect(loginSource).toContain('background: var(--color-surface-canvas)');
		expect(loginSource).not.toMatch(rawPaletteClassPattern);
	});

	it('redirects protected auth failures to /login while leaving public shellless routes explicit', () => {
		expect(layoutSource).toContain("const publicRoutes = ['/', '/login', '/auth/gitlab/callback'];");
		expect(layoutSource).toContain("const shelllessRoutes = ['/', '/login', '/auth/gitlab/callback', '/select-project'];");
		expect(layoutSource).toContain("goto('/login', { replaceState: true })");
		expect(layoutSource).toContain('{#if showAppChrome}');
		expect(clientSource).toContain("const AUTH_PUBLIC_PATHS = new Set(['/', '/login', '/auth/gitlab/callback']);");
		expect(clientSource).toContain("await goto('/login', { replaceState: true })");
		expect(hooksSource).toContain("const PUBLIC_PATHS = ['/', '/login', '/auth/gitlab/callback'];");
		expect(callbackSource).toContain('href="/login"');
		expect(layoutCssSource).toContain('font-family: "MaruBuri";');
		expect(layoutCssSource).toContain("url('/fonts/maruburi/MaruBuri-Regular.ttf')");
		expect(layoutCssSource).toContain('--font-sans: "MaruBuri", "Geist", Inter, system-ui, sans-serif;');
		expect(layoutCssSource).toContain('font-family: var(--font-sans);');
	});

	it('exposes the tutorial entry CTA and mounts the tour launcher', () => {
		expect(landingComponentSource).toContain('href="/dashboard?tutorial=on"');
		expect(landingComponentSource).toContain('튜토리얼 체험');
		expect(layoutSource).toContain("import TutorialController from '$lib/tutorial/TutorialController.svelte';");
		expect(layoutSource).toContain('<TutorialController />');
		expect(layoutCssSource).toContain('.driver-popover.afterglow-tour');
	});
});
