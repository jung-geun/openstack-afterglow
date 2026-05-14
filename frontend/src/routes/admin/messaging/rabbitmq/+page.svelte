<script lang="ts">
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="인프라 서비스 / RABBITMQ" title="RabbitMQ 메트릭" />

	<div class="mt-2">
		<p class="text-xs text-gray-500 mb-4">
			rabbitmq_prometheus 플러그인을 통해 수집된 메트릭입니다.
		</p>
		<GrafanaEmbed dashboardKey="rabbitmq" height={600} />
	</div>
</div>
