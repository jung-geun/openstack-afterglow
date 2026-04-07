<script lang="ts">
	import { page } from '$app/stores';

	const sections = $state([
		{
			label: 'Compute',
			prefix: '/admin/instances',
			open: false,
			items: [
				{ label: '전체 인스턴스', href: '/admin/instances' },
				{ label: '하이퍼바이저', href: '/admin/hypervisors' },
			],
		},
		{
			label: '스토리지',
			prefix: '/admin/volumes',
			open: false,
			items: [
				{ label: '전체 볼륨', href: '/admin/volumes' },
				{ label: '공유 스토리지', href: '/admin/shares' },
			],
		},
		{
			label: '네트워크',
			prefix: '/admin/topology',
			open: false,
			items: [
				{ label: '토폴로지', href: '/admin/topology' },
			],
		},
		{
			label: '컨테이너',
			prefix: '/admin/containers',
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
</script>

<aside class="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col overflow-y-auto">
	<nav class="flex-1 px-3 py-4 space-y-0.5">
		<!-- 개요 -->
		<a
			href="/admin"
			class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname === '/admin' ? 'bg-blue-600/20 text-blue-400 font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
		>
			개요
		</a>

		<!-- 섹션들 -->
		{#each sections as section}
			<div>
				<button
					onclick={() => section.open = !section.open}
					class="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm transition-colors {$page.url.pathname.startsWith(section.prefix) || section.items.some(item => $page.url.pathname.startsWith(item.href)) ? 'text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}"
				>
					<span>{section.label}</span>
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
</aside>
