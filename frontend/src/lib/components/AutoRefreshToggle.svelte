<script lang="ts">
	let { active = $bindable(false), intervalSeconds = 10 }: {
		active: boolean;
		intervalSeconds?: number;
	} = $props();
</script>

<button
	onclick={() => active = !active}
	class="flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium transition-all {active
		? 'border-blue-500 bg-blue-900/20 text-blue-400'
		: 'border-gray-700 bg-gray-900 text-gray-400 hover:border-gray-500'}"
	title="자동 새로고침 ({intervalSeconds}초)"
>
	<span class="inline-block {active ? 'animate-spin' : ''}" style="animation-duration:3s">⟳</span>
	자동
</button>
