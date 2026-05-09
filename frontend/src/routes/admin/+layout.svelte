<script lang="ts">
	import { goto } from '$app/navigation';
	import { isAdmin, auth } from '$lib/stores/auth';
	import AdminSidebar from '$lib/components/AdminSidebar.svelte';

	let redirecting = $state(false);

	$effect(() => {
		// 인증 정보 로딩 완료 후 권한 체크
		if ($auth.token !== null && !$isAdmin) {
			redirecting = true;
			setTimeout(() => goto('/dashboard'), 2000);
		}
	});

	let { children } = $props();
</script>

{#if $auth.token === null}
	<!-- 로딩 중: 빈 화면 -->
{:else if redirecting || !$isAdmin}
	<div class="flex flex-col items-center justify-center min-h-screen bg-gray-950 text-gray-300">
		<div class="text-6xl font-bold text-gray-600 mb-4">404</div>
		<div class="text-xl font-semibold text-gray-400 mb-2">페이지를 찾을 수 없습니다</div>
		<div class="text-sm text-gray-500">접근 권한이 없거나 존재하지 않는 페이지입니다.</div>
		<div class="text-xs text-gray-600 mt-4">잠시 후 대시보드로 이동합니다...</div>
	</div>
{:else}
	<div class="flex min-h-screen">
		<AdminSidebar />
		<main class="flex-1 overflow-auto min-w-0 pt-14">
			{@render children()}
		</main>
	</div>
{/if}
