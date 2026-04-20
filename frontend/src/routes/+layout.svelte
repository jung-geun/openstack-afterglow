<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth, isLoggedIn, isAdmin, clearAuth } from '$lib/stores/auth';
	import { theme, resolvedTheme } from '$lib/stores/theme';
	import { api } from '$lib/api/client';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import SettingsModal from '$lib/components/SettingsModal.svelte';
	import { siteConfig, loadSiteConfig } from '$lib/config/site';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import { deriveBreadcrumb } from '$lib/config/routes';
	import './layout.css';

	let { children } = $props();

	let settingsOpen = $state(false);

	// breadcrumb + title from URL
	const crumb = $derived(deriveBreadcrumb($page.url.pathname));

	// User initials for avatar
	const initials = $derived(
		($auth.username ?? 'U').slice(0, 2).toUpperCase()
	);

	const publicRoutes = ['/', '/auth/gitlab/callback'];

	let sessionWarning = $state(false);
	let sessionExpired = $state(false);
	let sessionRemaining = $state(0);
	let extendingSession = $state(false);

	$effect(() => {
		if (!$isLoggedIn && !publicRoutes.includes($page.url.pathname)) {
			goto('/');
		}
	});

	// 토큰이 설정되면 (로그인 직후 포함) 서버에서 권한 검증
	let lastVerifiedToken: string | null = null;
	$effect(() => {
		const token = $auth.token;
		const projectId = $auth.projectId;
		if (!token || token === lastVerifiedToken) return;
		lastVerifiedToken = token;
		(async () => {
			try {
				const me = await api.get<{ user_id: string; username: string; project_id: string; project_name: string; roles: string[]; is_system_admin: boolean }>(
					'/api/auth/me', token, projectId ?? undefined,
				);
				auth.update((s) => ({ ...s, isSystemAdmin: me.is_system_admin === true, roles: me.roles ?? s.roles }));
			} catch {
				clearAuth();
			}
		})();
	});

	onMount(() => {
		loadSiteConfig();

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

	async function logout() {
		// best-effort 서버 토큰 폐기
		if ($auth.token) {
			try {
				await api.post('/api/auth/logout', {}, $auth.token, $auth.projectId ?? undefined);
			} catch { /* 실패해도 로컬 정리는 진행 */ }
		}
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
	<nav class="fixed top-0 left-0 right-0 z-50 bg-[#0B1220] border-b border-gray-800 h-14 flex items-center px-4 md:px-6 gap-4 shrink-0">
		<!-- 모바일 햄버거 -->
		<button
			onclick={() => sidebarOpen.toggle()}
			class="md:hidden p-1.5 text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-800 shrink-0"
			aria-label="메뉴 열기"
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
			</svg>
		</button>

		<!-- 브레드크럼 + 페이지 제목 -->
		<div class="hidden md:block min-w-0">
			{#if crumb.breadcrumb}
				<div class="text-[10px] text-gray-500 uppercase tracking-widest font-medium leading-none mb-0.5">{crumb.breadcrumb}</div>
			{/if}
			<div class="text-white text-[15px] font-semibold leading-tight truncate">{crumb.title || $siteConfig.site_name}</div>
		</div>

		<!-- 검색 입력 -->
		<div class="flex-1 max-w-sm mx-4 hidden md:block relative">
			<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/></svg>
			</span>
			<input
				type="search"
				placeholder="리소스 검색..."
				class="w-full bg-gray-900 border border-gray-800 text-gray-200 rounded-lg pl-8 pr-3 py-1.5 text-[13px] outline-none focus:border-gray-700 placeholder-gray-600"
			/>
		</div>

		<!-- 우측 컨트롤 -->
		<div class="ml-auto flex items-center gap-2.5">
			{#if !$page.url.pathname.startsWith('/admin')}
				<div class="hidden lg:block"><ProjectSelector /></div>
			{/if}

			{#if $isAdmin}
				{#if $page.url.pathname.startsWith('/admin')}
					<a href="/dashboard"
						class="hidden md:flex items-center gap-1.5 px-3 h-8 rounded-lg border text-[12px] font-semibold transition-colors bg-amber-500/15 border-amber-600/50 text-amber-400 hover:bg-amber-500/25">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
						사용자 모드
					</a>
				{:else}
					<a href="/admin"
						class="hidden md:flex items-center gap-1.5 px-3 h-8 rounded-lg border text-[12px] font-semibold transition-colors bg-gray-900 border-gray-700 text-gray-200 hover:border-gray-600 hover:text-white">
						<svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-4z"/></svg>
						관리자 모드
					</a>
				{/if}
			{/if}

			<!-- 테마 토글 -->
			<button
				onclick={() => theme.toggle()}
				class="p-1.5 text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-800"
				title="{$theme === 'system' ? '시스템 테마' : $theme === 'dark' ? '다크 모드' : '라이트 모드'}"
			>
				{#if $theme === 'system'}
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
				{:else if $theme === 'dark'}
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
				{:else}
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 110 10A5 5 0 0112 7z"></path></svg>
				{/if}
			</button>

			<!-- 알림 아이콘 -->
			<button class="p-1.5 text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-800" title="알림">
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>
			</button>

			<!-- 유저 아바타 -->
			<button
				onclick={() => settingsOpen = true}
				class="w-[30px] h-[30px] rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-300 text-[11px] font-semibold hover:border-gray-600 transition-colors"
				title={$auth.username}
			>{initials}</button>
		</div>
	</nav>
	<main class="pt-14 min-h-screen bg-gray-950 text-white">
		{@render children()}
	</main>
	<SettingsModal bind:open={settingsOpen} onclose={() => settingsOpen = false} />
{:else}
	{@render children()}
{/if}
