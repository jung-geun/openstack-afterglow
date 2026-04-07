<script lang="ts">
	import { page } from '$app/stores';
	import { auth, isAdmin } from '$lib/stores/auth';
	import { sidebarOpen } from '$lib/stores/sidebar';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';

	const sections = $state([
		{
			label: 'Compute',
			prefix: '/dashboard/compute',
			open: false,
			items: [
				{ label: '인스턴스', href: '/dashboard/compute/instances' },
				{ label: '키페어', href: '/dashboard/compute/keypairs' },
				{ label: '이미지', href: '/dashboard/compute/images' },
			],
		},
		{
			label: '볼륨',
			prefix: '/dashboard/volumes',
			open: false,
			items: [
				{ label: '볼륨 목록', href: '/dashboard/volumes' },
				{ label: '볼륨 백업', href: '/dashboard/volumes/backups' },
				{ label: '볼륨 스냅샷', href: '/dashboard/volumes/snapshots' },
			],
		},
		{
			label: 'Share Storage',
			prefix: '/dashboard/shares',
			open: false,
			items: [
				{ label: '공유 스토리지', href: '/dashboard/shares' },
				{ label: '라이브러리 관리', href: '/dashboard/shares/manage' },
			],
		},
		{
			label: '컨테이너',
			prefix: '/dashboard/containers',
			open: false,
			items: [
				{ label: 'K8s 클러스터', href: '/dashboard/containers/clusters' },
				{ label: '컨테이너', href: '/dashboard/containers/instances' },
			],
		},
		{
			label: '네트워크',
			prefix: '/dashboard/network',
			open: false,
			items: [
				{ label: '토폴로지', href: '/dashboard/network/topology' },
				{ label: '네트워크', href: '/dashboard/network/networks' },
				{ label: '라우터', href: '/dashboard/network/routers' },
				{ label: '보안 그룹', href: '/dashboard/network/security-groups' },
				{ label: '로드밸런서', href: '/dashboard/network/loadbalancers' },
				{ label: 'Floating IP', href: '/dashboard/network/floating-ips' },
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
			대시보드
		</a>

		<!-- 섹션들 -->
		{#each sections as section}
			<div>
				<button
					onclick={() => section.open = !section.open}
					class="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith(section.prefix) ? 'text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
				>
					<span>{section.label}</span>
					<span class="text-xs text-gray-600">{section.open ? '▾' : '▸'}</span>
				</button>

				{#if section.open}
					<div class="ml-3 mt-0.5 space-y-0.5">
						{#each section.items as item}
							<a
								href={item.href}
								class="flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors {$page.url.pathname === item.href || ($page.url.pathname.startsWith(item.href + '/') && item.href !== '/dashboard/volumes') ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-500 hover:text-gray-200 hover:bg-gray-800'}"
							>
								{item.label}
							</a>
						{/each}
					</div>
				{/if}
			</div>
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
