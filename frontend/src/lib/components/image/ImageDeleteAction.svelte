<script lang="ts">
	import { useImageDetail } from '$lib/stores/imageDetail.svelte';

	const s = useImageDetail();
</script>

<div class="pt-2 pb-4">
	<button
		onclick={() => s.deleteImage()}
		disabled={s.deleting}
		class="w-full py-2 text-sm text-red-400 hover:text-red-300 disabled:text-gray-600 border border-red-900 hover:border-red-700 disabled:border-gray-700 rounded-lg transition-colors"
	>
		{s.deleting ? '삭제 중...' : '이미지 삭제'}
	</button>
</div>
