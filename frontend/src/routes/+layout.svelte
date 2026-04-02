<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth, isLoggedIn, clearAuth } from '$lib/stores/auth';
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();

	const publicRoutes = ['/'];

	$effect(() => {
		if (!$isLoggedIn && !publicRoutes.includes($page.url.pathname)) {
			goto('/');
		}
	});

	function logout() {
		clearAuth();
		goto('/');
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

{#if $isLoggedIn}
	<nav class="fixed top-0 left-0 right-0 z-50 bg-gray-900 border-b border-gray-700 h-14 flex items-center px-6 gap-6">
		<a href="/dashboard" class="text-white font-bold text-lg tracking-tight">Union</a>
		<a href="/dashboard" class="text-gray-300 hover:text-white text-sm transition-colors">대시보드</a>
		<a href="/create" class="text-gray-300 hover:text-white text-sm transition-colors">VM 생성</a>
		<a href="/admin" class="text-gray-300 hover:text-white text-sm transition-colors">관리</a>
		<div class="ml-auto flex items-center gap-4">
			<span class="text-gray-400 text-sm">{$auth.username} / {$auth.projectName}</span>
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
