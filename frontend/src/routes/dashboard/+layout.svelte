<script lang="ts">
	import { page } from '$app/stores';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import VmCreatePanel from '$lib/components/VmCreatePanel.svelte';
	import { wizardOpen } from '$lib/stores/wizard';
	let { children } = $props();
</script>

<!--
	컨테이너를 정확히 100vh + overflow-hidden 으로 가두고 main 을 자체 scroll container 로 만든다.
	이전 min-h-screen 구조에서는 컨텐츠가 길 때 main 이 늘어나 body 스크롤이 발생했고
	그 결과 main 안의 position:sticky 요소가 stick 하지 못했다(scroll ancestor 가 viewport 였음).
-->
<div class="flex h-screen overflow-hidden">
	<Sidebar />
	<main class="flex-1 overflow-y-auto min-w-0 pt-14">
		{@render children()}
	</main>
</div>

{#if $wizardOpen && !$page.data.mockup?.active}
	<VmCreatePanel />
{/if}
