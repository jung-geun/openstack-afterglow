<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { beforeNavigate, goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { get } from 'svelte/store';
	import { auth, authReady, isLoggedIn, isAdmin, clearAuth, logoutInProgress, enterMockAuth, exitMockAuth, getMockupProfile, isMockAuthActive } from '$lib/stores/auth';
	import { theme, resolvedTheme } from '$lib/stores/theme';
	import { api, getBaseUrl, refreshSession, beginSessionRevocation, endSessionRevocation } from '$lib/api/client';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import { siteConfig, initSiteConfig, qualifyBackendAssetPaths, replaceSiteConfig } from '$lib/config/site';
	import { resolveFaviconPath } from '$lib/config/brandAssets';
	import type { PublicSiteConfig } from '$lib/types/siteConfig';
	import type { AnnouncementUser, UnreadCountResponse } from '$lib/types/announcements';
	import { formatIsoDateTime } from '$lib/utils/format';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import { deriveBreadcrumb } from '$lib/config/routes';
	import Toast from '$lib/components/ui/Toast.svelte';
	import UploadDock from '$lib/components/UploadDock.svelte';
	import CmdPalette from '$lib/components/CmdPalette.svelte';
	import { palette } from '$lib/stores/palette';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import MockupBanner from '$lib/components/mockup/MockupBanner.svelte';
	import TutorialController from '$lib/tutorial/TutorialController.svelte';
	import { buildMockAuth } from '$lib/mockup/auth';
	import { MOCKUP_QUERY_KEY, MOCKUP_SESSION_KEY, MOCKUP_SERVICE_OVERRIDES, isMockupProfileId, isMockupPathAllowed, getMockupHomePath } from '$lib/mockup/contracts';
	import type { MockupProfileId } from '$lib/mockup/contracts';
	import './layout.css';

	let { children, data } = $props();
	const initialSiteConfig = untrack(() => data.siteConfig);
	const initialMockup = untrack(() => data.mockup);
	let themeReady = $state(false);
	let logoutConfirming = $state(false);
	let unreadAnnouncementCount = $state(0);
	let mockupClientReady = $state(false);
	let clientMockProfile = $state<MockupProfileId | null>(null);
	let enteredMockProfile: MockupProfileId | null = null;
	let previousMockupActive = initialMockup.active;
	let explicitMockupOff = false;
	let brandRefreshSerial = 0;
	const effectiveBrandTheme = $derived(themeReady ? $resolvedTheme : 'dark');
	const themedFaviconPath = $derived(resolveFaviconPath($siteConfig, effectiveBrandTheme));
	const mockup = $derived(data.mockup);
	const mockupAdminActive = $derived(mockup.active && mockup.profile === 'admin');
	let lastVerifiedToken: string | null = null;

	replaceSiteConfig(initialSiteConfig);

	async function refreshPublicSiteConfig() {
		const serial = ++brandRefreshSerial;
		try {
			const config = await api.get<Partial<PublicSiteConfig>>('/api/v1/site-config');
			if (serial !== brandRefreshSerial || mockup.active) return;
			initSiteConfig(qualifyBackendAssetPaths(config, getBaseUrl()));
		} catch {
			// Branding refresh is best effort; the server-provided config remains visible.
		}
	}

	async function refreshUnreadAnnouncementCount() {
		const token = $auth.token;
		const projectId = $auth.projectId;
		if (mockup.active || isMockAuthActive() || !token) return;
		try {
			const res = await api.get<UnreadCountResponse>('/api/v1/announcements/unread-count', token, projectId ?? undefined);
			unreadAnnouncementCount = res.unread_count;
		} catch {
			// 배지 갱신은 best-effort — 실패해도 헤더 렌더링을 막지 않는다.
		}
	}

	// 종 아이콘 드롭다운 — 최근 공지를 즉시 보여주고, 전체 목록은 알림함으로 이동
	let bellOpen = $state(false);
	let bellItems = $state<AnnouncementUser[] | null>(null);
	let bellError = $state(false);
	let bellContainer = $state<HTMLDivElement | null>(null);
	let bellButton = $state<HTMLButtonElement | null>(null);
	let bellFetchSerial = 0;

	function bellDotColor(severity: AnnouncementUser['severity']): string {
		if (severity === 'danger') return 'var(--color-state-danger)';
		if (severity === 'warning') return 'var(--color-state-warning)';
		return 'var(--color-accent)';
	}

	async function toggleBellDropdown() {
		bellOpen = !bellOpen;
		if (!bellOpen) return;
		bellError = false;
		bellItems = null;
		const serial = ++bellFetchSerial;
		const token = $auth.token;
		if (mockup.active || isMockAuthActive() || !token) {
			bellItems = [];
			return;
		}
		try {
			const items = await api.get<AnnouncementUser[]>('/api/v1/announcements', token, $auth.projectId ?? undefined);
			if (serial !== bellFetchSerial) return;
			bellItems = items.slice(0, 6);
			void refreshUnreadAnnouncementCount();
		} catch {
			if (serial !== bellFetchSerial) return;
			bellItems = [];
			bellError = true;
		}
	}

	function closeBellAndGo(id?: number) {
		bellOpen = false;
		void goto(id != null ? `/dashboard/notifications?focus=${id}` : '/dashboard/notifications');
	}

	$effect(() => {
		if (!bellOpen || typeof document === 'undefined') return;
		const onPointerDown = (event: MouseEvent) => {
			if (bellContainer && !bellContainer.contains(event.target as Node)) bellOpen = false;
		};
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key !== 'Escape') return;
			bellOpen = false;
			// 드롭다운 내부에 있던 키보드 포커스가 body로 떨어지지 않게 트리거로 복귀
			bellButton?.focus();
		};
		document.addEventListener('mousedown', onPointerDown);
		document.addEventListener('keydown', onKeyDown);
		return () => {
			document.removeEventListener('mousedown', onPointerDown);
			document.removeEventListener('keydown', onKeyDown);
		};
	});

	$effect.pre(() => {
		const active = mockup.active;
		if (active) {
			brandRefreshSerial += 1;
			initSiteConfig({ services: MOCKUP_SERVICE_OVERRIDES });
			if (mockupClientReady && mockup.profile && clientMockProfile === mockup.profile && enteredMockProfile !== mockup.profile) {
				if (!isMockAuthActive() || getMockupProfile() !== mockup.profile || !get(auth).token) {
					enterMockAuth(buildMockAuth(mockup.profile, $page.url.pathname), mockup.profile);
				}
				enteredMockProfile = mockup.profile;
			}
		} else if (explicitMockupOff) {
			lastVerifiedToken = null;
			if (isMockAuthActive()) exitMockAuth();
			void refreshPublicSiteConfig();
			enteredMockProfile = null;
			explicitMockupOff = false;
		} else if (
			mockupClientReady &&
			clientMockProfile &&
			isMockAuthActive() &&
			$page.url.searchParams.get(MOCKUP_QUERY_KEY) !== clientMockProfile
		) {
			const path = $page.url.pathname;
			const nextPath =
				(path.startsWith('/dashboard') || path.startsWith('/admin')) &&
				isMockupPathAllowed(clientMockProfile, path)
					? path
					: getMockupHomePath(clientMockProfile);
			void goto(`${nextPath}?${MOCKUP_QUERY_KEY}=${clientMockProfile}`, { replaceState: true });
		}
		previousMockupActive = active;
	});
	beforeNavigate(({ to, cancel }) => {
		if (typeof window === 'undefined' || !to?.url || to.url.origin !== location.origin) return;
		const requested = to.url.searchParams.get(MOCKUP_QUERY_KEY);
		if (requested === 'off') {
			sessionStorage.removeItem(MOCKUP_SESSION_KEY);
			clientMockProfile = null;
			explicitMockupOff = true;
			return;
		}
		if (isMockupProfileId(requested)) {
			sessionStorage.setItem(MOCKUP_SESSION_KEY, requested);
			clientMockProfile = requested;
			return;
		}
		const profile = clientMockProfile;
		if (!profile) return;
		const next = new URL(to.url);
		next.searchParams.set(MOCKUP_QUERY_KEY, profile);
		cancel();
		void goto(`${next.pathname}${next.search}${next.hash}`);
	});


	// breadcrumb + title from URL
	const crumb = $derived(deriveBreadcrumb($page.url.pathname));

	// User initials for avatar
	const initials = $derived(
		($auth.username ?? 'U').slice(0, 2).toUpperCase()
	);

	const publicRoutes = ['/', '/login', '/auth/gitlab/callback'];
	const projectAgnosticRoutes = ['/', '/login', '/auth/gitlab/callback', '/select-project'];

	const isInvitationRoute = $derived($page.url.pathname.startsWith('/invitations/'));
	const shelllessRoutes = ['/', '/login', '/auth/gitlab/callback', '/select-project'];
	const showAppChrome = $derived($isLoggedIn && !shelllessRoutes.includes($page.url.pathname) && !isInvitationRoute);

	$effect(() => {
		if (!mockupClientReady) return;
		if (!$logoutInProgress && !$isLoggedIn && !publicRoutes.includes($page.url.pathname) && !isInvitationRoute) {
			goto('/login', { replaceState: true });
		}
	});

	$effect(() => {
		if ($authReady && $isLoggedIn && !$auth.projectId && !projectAgnosticRoutes.includes($page.url.pathname) && !isInvitationRoute) {
			goto('/select-project');
		}
	});

	// 토큰이 설정되면 (로그인 직후 포함) 서버에서 권한 검증
	$effect(() => {
		const token = $auth.token;
		const projectId = $auth.projectId;
		if (mockup.active || isMockAuthActive() || !token || token === lastVerifiedToken) return;
		lastVerifiedToken = token;
		(async () => {
			try {
				const me = await api.get<{ user_id: string; username: string; project_id: string; project_name: string; roles: string[]; is_system_admin: boolean; auth_method?: string }>(
					'/api/v1/auth/me', token, projectId ?? undefined,
				);
				if (get(auth).token !== token || mockup.active || isMockAuthActive()) return;
				auth.update((s) => ({ ...s, isSystemAdmin: me.is_system_admin === true, roles: me.roles ?? s.roles, federated: me.auth_method === 'federated' }));
				authReady.set(true);
			} catch {
				if (get(auth).token === token && !mockup.active && !isMockAuthActive()) {
					authReady.set(false);
					clearAuth();
				}
			}
		})();
	});

	onMount(() => {
		themeReady = true;
		const requested = $page.url.searchParams.get(MOCKUP_QUERY_KEY);
		let bootstrapUrl: string | null = null;
		if (isMockupProfileId(requested)) {
			clientMockProfile = requested;
			sessionStorage.setItem(MOCKUP_SESSION_KEY, requested);
			if ((location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/admin')) && !isMockupPathAllowed(requested, location.pathname)) {
				bootstrapUrl = `${getMockupHomePath(requested)}?${MOCKUP_QUERY_KEY}=${requested}`;
			}
		} else if (requested === 'off') {
			sessionStorage.removeItem(MOCKUP_SESSION_KEY);
			clientMockProfile = null;
			explicitMockupOff = true;
		} else {
			const stored = sessionStorage.getItem(MOCKUP_SESSION_KEY);
			if (isMockupProfileId(stored)) {
				clientMockProfile = stored;
				const nextPath = (location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/admin')) && isMockupPathAllowed(stored, location.pathname)
					? location.pathname
					: getMockupHomePath(stored);
				bootstrapUrl = `${nextPath}?${MOCKUP_QUERY_KEY}=${stored}`;
			}
		}
		if (clientMockProfile && !isMockAuthActive()) {
			lastVerifiedToken = null;
			enterMockAuth(buildMockAuth(clientMockProfile, $page.url.pathname), clientMockProfile);
			enteredMockProfile = clientMockProfile;
		}
		mockupClientReady = true;
		if (bootstrapUrl) void goto(bootstrapUrl, { replaceState: true });
		if (!mockup.active && !bootstrapUrl) void refreshPublicSiteConfig();

		// access JWT 만료 2분 전에 자동 갱신 (client.ts의 401 재시도 보완)
		const interval = setInterval(async () => {
			if (mockup.active || !$auth.token || !$auth.refreshToken) return;
			const expiresAt = $auth.accessExpiresAt;
			if (!expiresAt) return;
			const remaining = expiresAt - Math.floor(Date.now() / 1000);
			if (remaining < 120) {
				try {
					await refreshSession();
				} catch {
					// refresh 실패 시 client.ts의 401 흐름이 처리
				}
			}
		}, 60_000);

		// 헤더 종 아이콘 미읽음 배지 — 60초 주기 폴링 (SSE 도입 전까지)
		void refreshUnreadAnnouncementCount();
		const announcementInterval = setInterval(() => void refreshUnreadAnnouncementCount(), 60_000);

		return () => {
			clearInterval(interval);
			clearInterval(announcementInterval);
		};
	});

	// 테마 변경 시 <html> 클래스 업데이트
	$effect(() => {
		if (typeof document === 'undefined') return;
		document.documentElement.classList.toggle('light', themeReady && $resolvedTheme === 'light');
	});

	async function logout() {
		if ($logoutInProgress || logoutConfirming) return;
		logoutConfirming = true;
		let confirmed: boolean;
		try {
			confirmed = await confirmDialog('로그아웃하시겠습니까?');
		} finally {
			logoutConfirming = false;
		}
		if (!confirmed) return;

		logoutInProgress.set(true);
		try {
			const pendingRefresh = beginSessionRevocation();
			await pendingRefresh;
			const logoutToken = $auth.token;
			if (logoutToken) {
				try {
					await api.post('/api/v1/auth/logout', {}, logoutToken, $auth.projectId ?? undefined);
				} catch { /* 실패해도 로컬 정리는 진행 */ }
			}
			const mockLogout = isMockAuthActive();
			if (mockLogout) {
				exitMockAuth();
				clientMockProfile = null;
				enteredMockProfile = null;
			}
			clearAuth();
			await goto(mockLogout ? '/login?tutorial=off' : '/login', { replaceState: true });
			toast.success('정상적으로 로그아웃 되었습니다.');
		} finally {
			endSessionRevocation();
			logoutInProgress.set(false);
		}
	}
</script>

<svelte:head><link rel="icon" href={themedFaviconPath} /></svelte:head>

{#if showAppChrome}
	<nav class="fixed top-0 left-0 md:left-60 right-0 z-50 bg-[#0B1220] border-b border-gray-800 h-14 flex items-center px-4 md:px-6 gap-4 shrink-0">
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

		<!-- 검색 입력 (⌘K 트리거) -->
		<button
			onclick={() => palette.open()}
			class="flex-1 max-w-sm mx-4 hidden lg:flex items-center gap-2 bg-gray-900 border border-gray-800 text-gray-500 rounded-lg pl-3 pr-2 py-1.5 text-[13px] hover:border-gray-700 transition-colors cursor-text"
			aria-label="검색 (⌘K)"
		>
			<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/></svg>
			<span class="flex-1 text-left text-gray-600">리소스 검색...</span>
			<kbd class="text-[10px] border border-gray-700 px-1.5 py-0.5 rounded font-mono text-gray-600">⌘K</kbd>
		</button>

		<!-- 우측 컨트롤 -->
		<div class="ml-auto flex items-center gap-2.5">
			{#if !$page.url.pathname.startsWith('/admin')}
				<div class="hidden lg:block"><ProjectSelector direction="down" /></div>
			{/if}

			{#if $isAdmin && !mockupAdminActive}
				{#if $page.url.pathname.startsWith('/admin')}
					<a href="/dashboard"
						class="hidden lg:flex items-center gap-1.5 px-3 h-8 rounded-lg border text-[12px] font-semibold transition-colors bg-amber-500/15 border-amber-600/50 text-amber-400 hover:bg-amber-500/25">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
						사용자 모드
					</a>
				{:else}
					<a href="/admin"
						class="hidden lg:flex items-center gap-1.5 px-3 h-8 rounded-lg border text-[12px] font-semibold transition-colors bg-gray-900 border-gray-700 text-gray-200 hover:border-gray-600 hover:text-white">
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

			<!-- 알림 아이콘 + 드롭다운 -->
			<div class="relative" bind:this={bellContainer}>
				<button
					bind:this={bellButton}
					onclick={toggleBellDropdown}
					class="relative p-1.5 text-gray-400 hover:text-white transition-colors rounded-md hover:bg-gray-800"
					title="알림"
					aria-haspopup="true"
					aria-expanded={bellOpen}
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>
					{#if unreadAnnouncementCount > 0}
						<span
							class="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full text-white text-[9px] font-semibold flex items-center justify-center leading-none"
							style="background: var(--color-state-danger);"
						>{unreadAnnouncementCount > 99 ? '99+' : unreadAnnouncementCount}</span>
					{/if}
				</button>
				{#if bellOpen}
					<!-- 모바일: 바텀 시트 / sm 이상: 종 아이콘 기준 드롭다운 (ProjectSelector 패턴 준용) -->
					<div
						class="fixed left-0 bottom-0 w-full rounded-t-xl sm:absolute sm:left-auto sm:right-0 sm:bottom-auto sm:top-full sm:mt-2 sm:w-80 sm:rounded-xl border shadow-xl z-50 overflow-hidden"
						style="background: var(--color-surface-raised); border-color: var(--color-line);"
					>
						<p class="px-4 pt-3 pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">알림</p>
						{#if bellItems === null}
							<p class="px-4 pb-3 text-xs text-[var(--color-ink-3)]">불러오는 중…</p>
						{:else if bellError}
							<p class="px-4 pb-3 text-xs text-[var(--color-state-danger)]">알림을 불러오지 못했습니다</p>
						{:else if bellItems.length === 0}
							<p class="px-4 pb-3 text-xs text-[var(--color-ink-3)]">받은 공지가 없습니다</p>
						{:else}
							<ul class="max-h-80 overflow-y-auto">
								{#each bellItems as item (item.id)}
									<li>
										<button
											onclick={() => closeBellAndGo(item.id)}
											class="w-full text-left px-4 py-2.5 flex items-start gap-2.5 hover:bg-[var(--color-surface-sunken)] transition-colors"
										>
											<span class="mt-1.5 w-2 h-2 rounded-full flex-shrink-0" style="background: {bellDotColor(item.severity)};"></span>
											<span class="flex-1 min-w-0">
												<span class="block text-xs text-[var(--color-ink-0)] truncate {item.is_read ? '' : 'font-semibold'}">{item.title}</span>
												<span class="block text-[10px] text-[var(--color-ink-3)] mt-0.5 tabular-nums">{formatIsoDateTime(item.created_at)}</span>
											</span>
											{#if !item.is_read}
												<span class="mt-1 text-[9px] uppercase tracking-wide text-[var(--color-accent)] flex-shrink-0">new</span>
											{/if}
										</button>
									</li>
								{/each}
							</ul>
						{/if}
						<div class="border-t" style="border-color: var(--color-line);">
							<button
								onclick={() => closeBellAndGo()}
								class="w-full px-4 py-2.5 text-xs text-center text-[var(--color-accent)] hover:bg-[var(--color-surface-sunken)] transition-colors"
							>전체 알림 보기</button>
						</div>
					</div>
				{/if}
			</div>

			<!-- 유저 아바타 -->
			<a
				href={mockupAdminActive ? '/admin' : '/dashboard/account'}
				class="w-[30px] h-[30px] rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-300 text-[11px] font-semibold hover:border-gray-600 transition-colors"
				title={$auth.username}
			>{initials}</a>

			<!-- 로그아웃 -->
			<button
				onclick={logout}
				disabled={$logoutInProgress}
				aria-label="로그아웃"
				class="p-1.5 text-gray-400 hover:text-red-400 transition-colors rounded-md hover:bg-gray-800"
				title="로그아웃"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
			</button>
		</div>
	</nav>
	{#if !mockup.active}
		<UploadDock />
	{/if}
	{#if !mockup.active || mockupAdminActive}
		<CmdPalette />
	{/if}
{/if}

{#if $isLoggedIn}
	<ConfirmDialog />
{/if}
{#if mockup.active}
	<MockupBanner label={mockup.bannerLabel} message={mockup.bannerMessage} />
{/if}
{#if $isLoggedIn}
	<TutorialController />
{/if}
<Toast />

<!-- children은 단일 렌더 포인트에서 항상 렌더 — 분기 전환 시 컴포넌트 재마운트 방지 -->
<main class="min-h-screen bg-gray-950 text-white">
	{@render children()}
</main>
