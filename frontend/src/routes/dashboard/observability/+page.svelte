<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="DASHBOARD / OBSERVABILITY" title="VM 메트릭" />

	{#if !$auth.projectId}
		<div class="mt-4 text-sm text-gray-500">
			프로젝트를 선택하면 VM 메트릭이 표시됩니다.
		</div>
	{:else}
		<div class="mt-2">
			<GrafanaEmbed
				dashboardKey="node"
				vars={{ project_id: $auth.projectId }}
				range="now-3h"
				height={600}
				desktopHeight={1400}
				title="Node Exporter"
			/>
		</div>
	{/if}
</div>
