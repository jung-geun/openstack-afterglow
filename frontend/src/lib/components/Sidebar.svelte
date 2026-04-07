<script lang="ts">
	import { page } from '$app/stores';
	import { isAdmin } from '$lib/stores/auth';

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
</script>

<aside class="w-60 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col overflow-y-auto">
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

	<!-- 하단: 관리 (admin 역할 보유 시에만 표시) -->
	{#if $isAdmin}
	<div class="p-3 border-t border-gray-800">
		<a
			href="/admin"
			class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith('/admin') ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
		>
			관리
		</a>
	</div>
	{/if}
</aside>
