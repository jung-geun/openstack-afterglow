<script lang="ts">
	import { page } from '$app/stores';
	import { auth, isAdmin } from '$lib/stores/auth';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import { siteConfig } from '$lib/config/site';
	import { openWizard } from '$lib/stores/wizard';
	import { palette } from '$lib/stores/palette';
	import RingMark from '$lib/components/ui/RingMark.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	let dashboardOpen = $state(false);

	const sections = $state([
		{
			label: 'Compute',
			prefix: '/dashboard/compute',
			extraPrefixes: [] as string[],
			icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2',
			open: false,
			items: [
				{ label: '인스턴스', href: '/dashboard/compute/instances', service: null },
				{ label: '이미지', href: '/dashboard/compute/images', service: null },
			],
		},
		{
			label: '볼륨',
			prefix: '/dashboard/volumes',
			extraPrefixes: [] as string[],
			icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4',
			open: false,
			items: [
				{ label: '볼륨 목록', href: '/dashboard/volumes', service: null },
				{ label: '볼륨 백업', href: '/dashboard/volumes/backups', service: null },
				{ label: '볼륨 스냅샷', href: '/dashboard/volumes/snapshots', service: null },
			],
		},
		{
			label: 'File Storage',
			prefix: '/dashboard/file-storage',
			extraPrefixes: [] as string[],
			icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
			open: false,
			service: 'manila' as const,
			items: [
				{ label: '파일 스토리지', href: '/dashboard/file-storage', service: null },
				{ label: '스냅샷', href: '/dashboard/file-storage/snapshots', service: null },
				{ label: 'Share 네트워크', href: '/dashboard/file-storage/networks', service: null },
				{ label: 'Security Service', href: '/dashboard/file-storage/security-services', service: null },
			],
		},
		{
			label: '라이브러리',
			prefix: '/dashboard/library',
			extraPrefixes: ['/dashboard/file-storage/manage'],
			icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
			open: false,
			items: [
				{ label: '레이어 카탈로그', href: '/dashboard/library', service: null },
				{ label: '템플릿', href: '/dashboard/library/templates', service: null },
				{ label: '라이브러리 관리', href: '/dashboard/file-storage/manage', service: null },
			],
		},
		{
			label: '컨테이너',
			prefix: '/dashboard/containers',
			extraPrefixes: ['/dashboard/drover'],
			icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
			open: false,
			service: 'containers' as const,
			items: [
				{ label: 'K8s 클러스터', href: '/dashboard/containers/clusters', service: 'magnum' as const },
				{ label: '컨테이너', href: '/dashboard/containers/instances', service: 'zun' as const },
				{ label: 'Drover', href: '/dashboard/drover', service: 'k3s' as const },
			],
		},
		{
			label: 'Database',
			prefix: '/dashboard/database',
			extraPrefixes: [] as string[],
			icon: 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3M4 7v5c0 1.657 3.582 3 8 3s8-1.343 8-3V7M4 7c0 1.657 3.582 3 8 3s8-1.343 8-3M4 12v5c0 1.657 3.582 3 8 3s8-1.343 8-3v-5',
			open: false,
			service: 'trove' as const,
			items: [
				{ label: 'DB 인스턴스', href: '/dashboard/database/instances', service: null },
			],
		},
		{
			label: 'Object Storage',
			prefix: '/dashboard/object-storage',
			extraPrefixes: [] as string[],
			icon: 'M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z',
			open: false,
			service: 'swift' as const,
			items: [
				{ label: '버킷', href: '/dashboard/object-storage/buckets', service: null },
			],
		},
		{
			label: 'Key Manager',
			prefix: '/dashboard/secrets',
			extraPrefixes: [] as string[],
			icon: 'M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z',
			open: false,
			items: [
				{ label: '비밀 관리', href: '/dashboard/secrets', service: null },
			],
		},
		{
			label: '네트워크',
			prefix: '/dashboard/network',
			extraPrefixes: [] as string[],
			icon: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
			open: false,
			items: [
				{ label: '네트워크', href: '/dashboard/network/networks', service: null },
				{ label: 'Floating IP', href: '/dashboard/network/floating-ips', service: null },
				{ label: '라우터', href: '/dashboard/network/routers', service: null },
				{ label: '로드밸런서', href: '/dashboard/network/loadbalancers', service: null },
				{ label: '보안 그룹', href: '/dashboard/network/security-groups', service: null },
			],
		},
	]);

	$effect(() => {
		const pathname = $page.url.pathname;
		const dashboardPaths = ['/dashboard/usage', '/dashboard/usage-report', '/dashboard/activity'];
		if (pathname === '/dashboard' || dashboardPaths.some((p) => pathname.startsWith(p))) {
			dashboardOpen = true;
		}
		for (const section of sections) {
			if (
				pathname.startsWith(section.prefix) ||
				section.extraPrefixes.some((p) => pathname.startsWith(p))
			) {
				section.open = true;
			}
		}
	});

	// 페이지 이동 시 모바일 드로어 자동 닫기
	$effect(() => {
		$page.url.pathname;
		sidebarOpen.close();
	});

	function isSectionVisible(section: { service?: string }): boolean {
		const svcs = $siteConfig.services as Record<string, boolean> | undefined;
		if (!section.service) return true;
		if (section.service === 'manila') return svcs?.manila ?? false;
		if (section.service === 'containers') return (svcs?.magnum ?? false) || (svcs?.zun ?? false) || (svcs?.k3s ?? false);
		return svcs?.[section.service] ?? false;
	}

	function isItemVisible(item: { service?: string | null }): boolean {
		const svcs = $siteConfig.services;
		if (!item.service) return true;
		if (item.service === 'magnum') return svcs?.magnum ?? false;
		if (item.service === 'zun') return svcs?.zun ?? false;
		if (item.service === 'k3s') return svcs?.k3s ?? false;
		return true;
	}
</script>

<!-- 오버레이 배경 (모바일만) -->
{#if $sidebarOpen}
	<button
		class="fixed inset-0 z-30 bg-black/50 md:hidden"
		onclick={() => sidebarOpen.close()}
		aria-label="메뉴 닫기"
	></button>
{/if}

<aside class="fixed top-0 left-0 bottom-0 z-30 w-60 bg-gray-900 border-r border-gray-800 flex flex-col overflow-y-auto transition-transform duration-200 ease-in-out {$sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:sticky md:top-0 md:h-screen md:translate-x-0 md:shrink-0 md:transition-none">
	<!-- 로고 헤더 -->
	<div class="h-14 flex items-center gap-2.5 px-4 border-b border-gray-800 shrink-0">
		<!-- RingMark logo -->
		<RingMark size={26} />
		<a href="/dashboard" class="text-white font-bold text-base tracking-tight hover:text-gray-200 transition-colors">
			{$siteConfig.site_name}
		</a>
	</div>

	<!-- VM 생성 버튼 -->
	<div class="p-3">
		<Button onclick={openWizard} class="w-full">
			<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14M5 12h14"/></svg>
			VM 생성
		</Button>
	</div>

	<!-- 검색 버튼 (1024px 미만에서만 표시) -->
	<div class="px-3 pb-2 lg:hidden">
		<button
			onclick={() => palette.open()}
			class="w-full flex items-center gap-2 bg-gray-800 border border-gray-700 text-gray-500 rounded-lg pl-3 pr-2 py-1.5 text-[13px] hover:border-gray-600 transition-colors cursor-text"
			aria-label="검색 (⌘K)"
		>
			<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/></svg>
			<span class="flex-1 text-left text-gray-600">리소스 검색...</span>
			<kbd class="text-[10px] border border-gray-700 px-1.5 py-0.5 rounded font-mono text-gray-600">⌘K</kbd>
		</button>
	</div>

	<nav class="flex-1 px-3 pb-4 space-y-0.5">
		<!-- 대시보드 섹션 -->
		<div>
			<button
				onclick={() => dashboardOpen = !dashboardOpen}
				class="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname === '/dashboard' || ['/dashboard/usage', '/dashboard/usage-report', '/dashboard/activity'].some((p) => $page.url.pathname.startsWith(p)) ? 'text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
			>
				<div class="flex items-center gap-1.5">
					<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
					<span>대시보드</span>
				</div>
				<span class="text-xs text-gray-600">{dashboardOpen ? '▾' : '▸'}</span>
			</button>
			{#if dashboardOpen}
				<div class="ml-3 mt-0.5 space-y-0.5">
					<a href="/dashboard" class="nav-item nav-sub flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors" class:nav-active={$page.url.pathname === '/dashboard'}>개요</a>
					<a href="/dashboard/usage" class="nav-item nav-sub flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors" class:nav-active={$page.url.pathname.startsWith('/dashboard/usage') && !$page.url.pathname.startsWith('/dashboard/usage-report')}>사용량</a>
					<a href="/dashboard/usage-report" class="nav-item nav-sub flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors" class:nav-active={$page.url.pathname.startsWith('/dashboard/usage-report')}>사용량 리포트</a>
					<a href="/dashboard/activity" class="nav-item nav-sub flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors" class:nav-active={$page.url.pathname.startsWith('/dashboard/activity')}>활동</a>
				</div>
			{/if}
		</div>
		<a
			href="/dashboard/network/topology"
			class="nav-item flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors"
		class:nav-active={$page.url.pathname === '/dashboard/network/topology'}
		>
			<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
			토폴로지
		</a>
		<!-- 섹션들 -->
		{#each sections as section}
			{#if isSectionVisible(section)}
			<div>
				<button
					onclick={() => section.open = !section.open}
					class="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith(section.prefix) || section.extraPrefixes.some((p) => $page.url.pathname.startsWith(p)) ? 'text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
				>
					<div class="flex items-center gap-1.5">
						{#if section.icon}
							<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={section.icon}></path></svg>
						{/if}
						<span>{section.label}</span>
					</div>
					<span class="text-xs text-gray-600">{section.open ? '▾' : '▸'}</span>
				</button>

				{#if section.open}
					<div class="ml-3 mt-0.5 space-y-0.5">
						{#each section.items as item}
							{#if isItemVisible(item)}
							<a
								href={item.href}
								class="nav-item nav-sub flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors"
								class:nav-active={$page.url.pathname === item.href || ($page.url.pathname.startsWith(item.href + '/') && item.href !== '/dashboard/volumes')}
							>
								{item.label}
							</a>
							{/if}
						{/each}
					</div>
				{/if}
			</div>
			{/if}
		{/each}
	</nav>

	<!-- 하단: 프로젝트 정보 + 관리 -->
	<div class="border-t border-gray-800 shrink-0">
		<!-- 프로젝트 선택 (1024px 미만) -->
		<div class="p-3 lg:hidden">
			<div class="text-[10px] text-gray-500 uppercase tracking-wide px-1 mb-1.5">프로젝트</div>
			<ProjectSelector />
		</div>

		<!-- 프로젝트 이름 표시 (1024px 이상) -->
		<div class="hidden lg:block px-4 py-3">
			<div class="text-[10px] text-gray-500 uppercase tracking-widest font-medium">프로젝트</div>
			<div class="text-[13px] text-gray-200 font-medium mt-0.5 truncate">{$auth.projectName ?? '—'}</div>
			<a
				href="/dashboard/project-settings"
				class="inline-flex items-center gap-1 mt-1.5 text-[11px] transition-colors {$page.url.pathname === '/dashboard/project-settings' ? 'text-blue-400' : 'text-gray-500 hover:text-gray-300'}"
			>
				<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
				프로젝트 설정
			</a>
		</div>

		{#if $isAdmin}
			<div class="px-3 pb-3 lg:hidden">
				<!-- 1024px 미만: 관리/사용자 모드 전환 -->
				{#if $page.url.pathname.startsWith('/admin')}
					<a href="/dashboard"
						class="nav-item nav-active flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
						사용자 모드
					</a>
				{:else}
					<a href="/admin"
						class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-gray-400 hover:text-white hover:bg-gray-800">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-4z"></path></svg>
						관리자 모드
					</a>
				{/if}
			</div>
		{/if}

		<!-- 모바일 사용자 정보 -->
		<div class="p-3 pt-0 md:hidden border-t border-gray-800">
			<div class="px-3 text-xs text-gray-500">{$auth.username}</div>
		</div>
	</div>
</aside>

<style>
	.nav-item {
		color: var(--color-ink-2);
	}
	.nav-item:hover:not(.nav-active) {
		color: var(--color-ink-0);
		background-color: color-mix(in oklab, var(--color-surface-sunken) 80%, transparent);
	}
	.nav-sub {
		color: var(--color-ink-3);
	}
	.nav-sub:hover:not(.nav-active) {
		color: var(--color-ink-1);
	}
	.nav-active {
		background: var(--warm-soft);
		color: var(--color-warm-2);
		font-weight: 500;
		position: relative;
	}
	.nav-active::before {
		content: "";
		position: absolute;
		left: 0;
		top: 6px;
		bottom: 6px;
		width: 3px;
		border-radius: 2px;
		background: var(--color-warm);
	}

</style>
