<script lang="ts">
	import { page } from '$app/stores';
	import { auth, isAdmin } from '$lib/stores/auth';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import { siteConfig } from '$lib/config/site';

	const sections = $state([
		{
			label: 'Compute',
			prefix: '/dashboard/compute',
			icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2',
			open: false,
			items: [
				{ label: '인스턴스', href: '/dashboard/compute/instances', service: null },
				{ label: '키페어', href: '/dashboard/compute/keypairs', service: null },
				{ label: '이미지', href: '/dashboard/compute/images', service: null },
			],
		},
		{
			label: '볼륨',
			prefix: '/dashboard/volumes',
			icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4',
			open: false,
			items: [
				{ label: '볼륨 목록', href: '/dashboard/volumes', service: null },
				{ label: '볼륨 백업', href: '/dashboard/volumes/backups', service: null },
				{ label: '볼륨 스냅샷', href: '/dashboard/volumes/snapshots', service: null },
			],
		},
		{
			label: 'Share Storage',
			prefix: '/dashboard/shares',
			icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
			open: false,
			service: 'manila' as const,
			items: [
				{ label: '공유 스토리지', href: '/dashboard/shares', service: null },
				{ label: '라이브러리 관리', href: '/dashboard/shares/manage', service: null },
			],
		},
		{
			label: '컨테이너',
			prefix: '/dashboard/containers',
			icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
			open: false,
			service: 'containers' as const,
			items: [
				{ label: 'K8s 클러스터', href: '/dashboard/containers/clusters', service: 'magnum' as const },
				{ label: '컨테이너', href: '/dashboard/containers/instances', service: 'zun' as const },
			],
		},
		{
			label: '네트워크',
			prefix: '/dashboard/network',
			icon: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
			open: false,
			items: [
				{ label: '토폴로지', href: '/dashboard/network/topology', service: null },
				{ label: '네트워크', href: '/dashboard/network/networks', service: null },
				{ label: '라우터', href: '/dashboard/network/routers', service: null },
				{ label: '보안 그룹', href: '/dashboard/network/security-groups', service: null },
				{ label: '로드밸런서', href: '/dashboard/network/loadbalancers', service: null },
				{ label: 'Floating IP', href: '/dashboard/network/floating-ips', service: null },
			],
		},
	]);

	$effect(() => {
		const pathname = $page.url.pathname;
		for (const section of sections) {
			if (pathname.startsWith(section.prefix)) {
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
		const svcs = $siteConfig.services;
		if (!section.service) return true;
		if (section.service === 'manila') return svcs?.manila ?? false;
		if (section.service === 'containers') return (svcs?.magnum ?? false) || (svcs?.zun ?? false);
		return true;
	}

	function isItemVisible(item: { service?: string | null }): boolean {
		const svcs = $siteConfig.services;
		if (!item.service) return true;
		if (item.service === 'magnum') return svcs?.magnum ?? false;
		if (item.service === 'zun') return svcs?.zun ?? false;
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

<aside class="fixed top-14 left-0 bottom-0 z-30 w-60 bg-gray-900 border-r border-gray-800 flex flex-col overflow-y-auto transition-transform duration-200 ease-in-out {$sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:static md:translate-x-0 md:shrink-0 md:transition-none">
	<!-- VM 생성 버튼 -->
	<div class="p-4">
		<a
			href="/create"
			class="block w-full text-center bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
		>
			+ VM 생성
		</a>
	</div>

	<nav class="flex-1 px-3 pb-4 space-y-0.5">
		<!-- 대시보드 -->
		<a
			href="/dashboard"
			class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname === '/dashboard' ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
		>
			<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
			대시보드
		</a>
		<a
			href="/dashboard/my-resources"
			class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname === '/dashboard/my-resources' ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
		>
			<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
			내 리소스
		</a>

		<!-- 섹션들 -->
		{#each sections as section}
			{#if isSectionVisible(section)}
			<div>
				<button
					onclick={() => section.open = !section.open}
					class="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith(section.prefix) ? 'text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
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
								class="flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors {$page.url.pathname === item.href || ($page.url.pathname.startsWith(item.href + '/') && item.href !== '/dashboard/volumes') ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-500 hover:text-gray-200 hover:bg-gray-800'}"
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

	<!-- 하단: 모바일 전용 항목 + 관리 -->
	<div class="border-t border-gray-800">
		<!-- 프로젝트 선택 (모바일만) -->
		<div class="p-3 sm:hidden">
			<div class="text-xs text-gray-500 uppercase tracking-wide px-3 mb-1.5">프로젝트</div>
			<ProjectSelector />
		</div>

		{#if $isAdmin}
			<div class="p-3 pt-0 md:pt-3 md:border-t md:border-gray-800">
				<!-- 모바일: 관리/사용자 모드 전환 -->
				{#if $page.url.pathname.startsWith('/admin')}
					<a
						href="/dashboard"
						class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors bg-blue-600/20 text-blue-400 font-medium md:hidden"
					>
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
						사용자 모드
					</a>
				{:else}
					<a
						href="/admin"
						class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-gray-400 hover:text-white hover:bg-gray-800 md:hidden"
					>
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
						관리 모드
					</a>
				{/if}
				<!-- 데스크톱: 기존 관리 링크 -->
				<a
					href="/admin"
					class="hidden md:flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith('/admin') ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
				>
					관리
				</a>
			</div>
		{/if}

		<!-- 모바일 사용자 정보 -->
		<div class="p-3 pt-0 md:hidden">
			<div class="px-3 text-xs text-gray-500">{$auth.username}</div>
		</div>
	</div>
</aside>
