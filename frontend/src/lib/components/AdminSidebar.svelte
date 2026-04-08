<script lang="ts">
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';

	const sections = $state([
		{
			label: 'Compute',
			prefix: '/admin/instances',
			icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2',
			open: false,
			items: [
				{ label: '전체 인스턴스', href: '/admin/instances' },
				{ label: '하이퍼바이저', href: '/admin/hypervisors' },
			],
		},
		{
			label: '스토리지',
			prefix: '/admin/volumes',
			icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4',
			open: false,
			items: [
				{ label: '전체 볼륨', href: '/admin/volumes' },
				{ label: '공유 스토리지', href: '/admin/shares' },
			],
		},
		{
			label: '네트워크',
			prefix: '/admin/topology',
			icon: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
			open: false,
			items: [
				{ label: '토폴로지', href: '/admin/topology' },
				{ label: '네트워크', href: '/admin/networks' },
				{ label: 'Floating IP', href: '/admin/floating-ips' },
				{ label: '라우터', href: '/admin/routers' },
				{ label: '포트', href: '/admin/ports' },
			],
		},
		{
			label: '컨테이너',
			prefix: '/admin/containers',
			icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
			open: false,
			items: [
				{ label: '전체 컨테이너', href: '/admin/containers' },
			],
		},
	]);

	$effect(() => {
		const pathname = $page.url.pathname;
		for (const section of sections) {
			if (pathname.startsWith(section.prefix) || section.items.some(item => pathname.startsWith(item.href))) {
				section.open = true;
			}
		}
	});

	// 페이지 이동 시 모바일 드로어 자동 닫기
	$effect(() => {
		$page.url.pathname;
		sidebarOpen.close();
	});
</script>

<!-- 오버레이 배경 (모바일만) -->
{#if $sidebarOpen}
	<button
		class="fixed inset-0 z-30 bg-black/50 md:hidden"
		onclick={() => sidebarOpen.close()}
		aria-label="메뉴 닫기"
	></button>
{/if}

<aside class="fixed top-14 left-0 bottom-0 z-30 w-56 bg-gray-900 border-r border-gray-800 flex flex-col overflow-y-auto transition-transform duration-200 ease-in-out {$sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:static md:translate-x-0 md:shrink-0 md:transition-none">
	<nav class="flex-1 px-3 py-4 space-y-0.5">
		<!-- 개요 -->
		<a
			href="/admin"
			class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname === '/admin' ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
		>
			<svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
			개요
		</a>

		<!-- 섹션들 -->
		{#each sections as section}
			<div>
				<button
					onclick={() => section.open = !section.open}
					class="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith(section.prefix) || section.items.some(item => $page.url.pathname.startsWith(item.href)) ? 'text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
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
							<a
								href={item.href}
								class="flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors {$page.url.pathname === item.href ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-500 hover:text-gray-200 hover:bg-gray-800'}"
							>
								{item.label}
							</a>
						{/each}
					</div>
				{/if}
			</div>
		{/each}
	</nav>

	<!-- 하단: 모바일 전용 항목 -->
	<div class="border-t border-gray-800">
		<!-- 프로젝트 선택 (모바일만) -->
		<div class="p-3 sm:hidden">
			<div class="text-xs text-gray-500 uppercase tracking-wide px-3 mb-1.5">프로젝트</div>
			<ProjectSelector />
		</div>

		<!-- 사용자 모드 전환 (모바일만) -->
		<div class="p-3 pt-0 md:hidden">
			<a
				href="/dashboard"
				class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors bg-blue-600/20 text-blue-400 font-medium"
			>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
				사용자 모드
			</a>
		</div>

		<!-- 모바일 사용자 정보 -->
		<div class="p-3 pt-0 md:hidden">
			<div class="px-3 text-xs text-gray-500">{$auth.username}</div>
		</div>
	</div>
</aside>
