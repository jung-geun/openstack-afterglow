<script lang="ts">
  import { useVolumeDetail } from '$lib/stores/volumeDetail.svelte';
  import { formatStorage } from '$lib/utils/format';

  const s = useVolumeDetail();
</script>

<div class="bg-gray-900 rounded-xl border border-gray-700 p-4 mb-4 space-y-2 text-sm">
  <div class="flex justify-between">
    <span class="text-gray-400">ID</span>
    <span class="text-white font-mono text-xs">{s.volume!.id}</span>
  </div>
  <div class="flex justify-between">
    <span class="text-gray-400">크기</span>
    <span class="text-white">{formatStorage(s.volume!.size)}</span>
  </div>
  <div class="flex justify-between">
    <span class="text-gray-400">타입</span>
    <span class="text-white">{s.volume!.volume_type ?? '-'}</span>
  </div>
  <div class="flex justify-between">
    <span class="text-gray-400">연결</span>
    <span class="text-white">{s.volume!.attachments.length > 0 ? `${s.volume!.attachments.length}개 인스턴스` : '미연결'}</span>
  </div>
</div>
