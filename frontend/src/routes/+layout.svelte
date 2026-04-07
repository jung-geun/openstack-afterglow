<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth, isLoggedIn, isAdmin, clearAuth } from '$lib/stores/auth';
	import { theme, resolvedTheme } from '$lib/stores/theme';
	import { api } from '$lib/api/client';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import { siteConfig, loadSiteConfig } from '$lib/config/site';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import './layout.css';

	let { children } = $props();

	const publicRoutes = ['/'];

	let sessionWarning = $state(false);
	let sessionExpired = $state(false);
	let sessionRemaining = $state(0);
	let extendingSession = $state(false);

	$effect(() => {
		if (!$isLoggedIn && !publicRoutes.includes($page.url.pathname)) {
			goto('/');
		}
	});

	// localStorage에서 복원된 토큰의 유효성을 서버에서 검증
	onMount(() => {
		loadSiteConfig();
		(async () => {
			if ($auth.token) {
				try {
					await api.get('/api/auth/me', $auth.token, $auth.projectId ?? undefined);
				} catch {
					clearAuth();
					return;
				}
			}
		})();

		// 세션 타이머: 1분마다 남은 시간 체크
		const interval = setInterval(async () => {
			if (!$auth.token) return;
			try {
				const info = await api.get<{ remaining_seconds: number; warning_before_seconds: number }>(
					'/api/auth/session-info', $auth.token, $auth.projectId ?? undefined
				);
				sessionRemaining = info.remaining_seconds;
				if (info.remaining_seconds <= 0) {
					sessionExpired = true;
					sessionWarning = false;
					clearAuth();
					goto('/');
				} else if (info.remaining_seconds <= info.warning_before_seconds) {
					sessionWarning = true;
				} else {
					sessionWarning = false;
				}
			} catch {
				// 세션 체크 실패 시 무시
			}
		}, 60_000);

		return () => clearInterval(interval);
	});

	async function extendSession() {
		if (!$auth.token || extendingSession) return;
		extendingSession = true;
		try {
			await api.post('/api/auth/extend-session', {}, $auth.token, $auth.projectId ?? undefined);
			sessionWarning = false;
		} catch {
			// 연장 실패 시 무시
		} finally {
			extendingSession = false;
		}
	}

	function formatRemaining(seconds: number): string {
		const m = Math.floor(seconds / 60);
		const s = seconds % 60;
		return m > 0 ? `${m}분 ${s}초` : `${s}초`;
	}

	// 테마 변경 시 <html> 클래스 업데이트
	$effect(() => {
		if (typeof document === 'undefined') return;
		document.documentElement.classList.toggle('light', $resolvedTheme === 'light');
	});

	function logout() {
		clearAuth();
		goto('/');
	}
</script>

<svelte:head><link rel="icon" href={$siteConfig.favicon_path} /></svelte:head>

{#if $isLoggedIn}
	<!-- 세션 만료 경고 배너 -->
	{#if sessionWarning}
		<div class="fixed top-14 left-0 right-0 z-40 bg-yellow-900/90 border-b border-yellow-700 px-3 md:px-6 py-2 flex items-center gap-4 text-sm">
			<span class="text-yellow-200">세션이 <strong>{formatRemaining(sessionRemaining)}</strong> 후 만료됩니다.</span>
			<button
				onclick={extendSession}
				disabled={extendingSession}
				class="text-xs bg-yellow-700 hover:bg-yellow-600 text-white px-3 py-1 rounded transition-colors disabled:opacity-50"
			>{extendingSession ? '연장 중...' : '세션 연장'}</button>
			<button onclick={() => sessionWarning = false} class="ml-auto text-yellow-400 hover:text-yellow-200 text-xs">✕</button>
		</div>
	{/if}
	<nav class="fixed top-0 left-0 right-0 z-50 bg-gray-900 border-b border-gray-700 h-14 flex items-center px-3 md:px-6 gap-3 md:gap-6">
		<a href="/dashboard" class="flex items-center gap-2 text-white font-bold text-base md:text-lg tracking-tight">
			<img src={$siteConfig.logo_path} alt={$siteConfig.site_name} class="h-7 w-auto" />
			{$siteConfig.site_name}
		</a>
		<!-- 햄버거 버튼 (모바일만) -->
		<button
			onclick={() => sidebarOpen.toggle()}
			class="md:hidden p-1.5 text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-800"
			aria-label="메뉴 열기"
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
			</svg>
		</button>
		<div class="ml-auto flex items-center gap-3">
			<div class="hidden sm:block"><ProjectSelector /></div>
			{#if $isAdmin}
				{#if $page.url.pathname.startsWith('/admin')}
					<a href="/dashboard" class="hidden md:flex items-center gap-1.5 px-3 py-1 bg-gray-800 border border-blue-700 hover:border-blue-500 text-blue-400 hover:text-blue-300 text-xs rounded-md transition-colors">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
						사용자 모드
					</a>
				{:else}
					<a href="/admin" class="hidden md:flex items-center gap-1.5 px-3 py-1 bg-gray-800 border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white text-xs rounded-md transition-colors">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
						관리
					</a>
				{/if}
			{/if}
			<!-- 테마 토글 (system → dark → light 순환) -->
			<button
				onclick={() => theme.toggle()}
				class="p-1.5 text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-800"
				title="{$theme === 'system' ? '시스템 테마' : $theme === 'dark' ? '다크 모드' : '라이트 모드'}"
			>
				{#if $theme === 'system'}
					<!-- System icon -->
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
				{:else if $theme === 'dark'}
					<!-- Moon icon -->
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
				{:else}
					<!-- Sun icon -->
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 110 10A5 5 0 0112 7z"></path></svg>
				{/if}
			</button>
			<span class="hidden md:inline text-gray-400 text-sm">{$auth.username}</span>
			<button onclick={logout} class="text-gray-400 hover:text-white text-sm transition-colors">
				로그아웃
			</button>
		</div>
	</nav>
	<main class="pt-14 min-h-screen bg-gray-950 text-white">
		{@render children()}
	</main>
{:else}
	{@render children()}
{/if}
