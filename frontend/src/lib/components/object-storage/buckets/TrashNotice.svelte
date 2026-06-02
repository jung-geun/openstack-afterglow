<script lang="ts">
	let { retentionDays = 30 }: { retentionDays?: number } = $props();
</script>

<div class="mt-4 px-4 py-3 text-xs text-orange-400/80 bg-orange-950/20 border border-orange-900/50 rounded-lg">
	<strong class="text-orange-400">휴지통 안내:</strong>
	삭제된 파일은 <code>*-trash</code> 버킷에, 삭제된 버킷은 목록에서 숨겨져 <strong>{retentionDays}일</strong> 동안 보관됩니다.
	보관 기간 내에 복구할 수 있으며, 기간이 지나면 자동으로 영구 삭제됩니다.
	휴지통에 보관된 항목도 스토리지 용량을 차지합니다.
</div>
