<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth, isLoggedIn, clearAuth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();

	const publicRoutes = ['/'];

	let sessionWarning = $state(false);
	let sessionExpired = $state(false);
	let sessionRemaining = $state(0);
	let extendingSession = $state(false);

	$effect(() => {
		if (!$isLoggedIn && !publicRoutes.includes($page.url.pathname)) {
			goto('/');
		}
	});

	// localStorage에서 복원된 토큰의 유효성을 서버에서 검증
	onMount(async () => {
		if ($auth.token) {
			try {
				await api.get('/api/auth/me', $auth.token, $auth.projectId ?? undefined);
			} catch {
				clearAuth();
				return;
			}
		}

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

	function logout() {
		clearAuth();
		goto('/');
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

{#if $isLoggedIn}
	<!-- 세션 만료 경고 배너 -->
	{#if sessionWarning}
		<div class="fixed top-14 left-0 right-0 z-40 bg-yellow-900/90 border-b border-yellow-700 px-6 py-2 flex items-center gap-4 text-sm">
			<span class="text-yellow-200">세션이 <strong>{formatRemaining(sessionRemaining)}</strong> 후 만료됩니다.</span>
			<button
				onclick={extendSession}
				disabled={extendingSession}
				class="text-xs bg-yellow-700 hover:bg-yellow-600 text-white px-3 py-1 rounded transition-colors disabled:opacity-50"
			>{extendingSession ? '연장 중...' : '세션 연장'}</button>
			<button onclick={() => sessionWarning = false} class="ml-auto text-yellow-400 hover:text-yellow-200 text-xs">✕</button>
		</div>
	{/if}
	<nav class="fixed top-0 left-0 right-0 z-50 bg-gray-900 border-b border-gray-700 h-14 flex items-center px-6 gap-6">
		<a href="/dashboard" class="text-white font-bold text-lg tracking-tight">Union</a>
		<div class="ml-auto flex items-center gap-4">
			<ProjectSelector />
			<span class="text-gray-400 text-sm">{$auth.username}</span>
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
