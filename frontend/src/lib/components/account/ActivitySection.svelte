<script lang="ts">
	import ActivityLogTable from '$lib/components/admin/ActivityLogTable.svelte';
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
	<div class="text-white text-[15px] font-semibold mb-3">최근 활동</div>
	<ActivityLogTable endpoint="/api/v1/profile/activity" storageKey="account-activity" />
</div>
