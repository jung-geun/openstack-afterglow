<script lang="ts">
  import type { Volume } from '$lib/types/volume';
  import { formatStorage } from '$lib/utils/format';

  let { volume }: { volume: Volume } = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
  <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">기본 정보</h2>
  <dl class="grid grid-cols-2 gap-x-8 gap-y-3">
    <div>
      <dt class="text-xs text-gray-500 mb-0.5">ID</dt>
      <dd class="text-sm text-gray-300 font-mono">{volume.id}</dd>
    </div>
    <div>
      <dt class="text-xs text-gray-500 mb-0.5">크기</dt>
      <dd class="text-sm text-gray-300">{formatStorage(volume.size)}</dd>
    </div>
    <div>
      <dt class="text-xs text-gray-500 mb-0.5">볼륨 타입</dt>
      <dd class="text-sm text-gray-300">{volume.volume_type ?? '-'}</dd>
    </div>
  </dl>
</div>
