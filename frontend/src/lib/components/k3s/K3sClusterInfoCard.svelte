<script lang="ts">
  import { useK3sClusterDetail } from '$lib/stores/k3sClusterDetail.svelte';

  const s = useK3sClusterDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
  <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">클러스터 정보</h3>
  <dl class="space-y-1.5 text-sm">
    <div class="flex justify-between">
      <dt class="text-gray-400 text-xs">ID</dt>
      <dd class="font-mono text-xs text-gray-300">{s.cluster!.id.slice(0, 12)}...</dd>
    </div>
    <div class="flex justify-between">
      <dt class="text-gray-400 text-xs">API 주소</dt>
      <dd class="text-gray-300 font-mono text-xs">{s.cluster!.api_address || '-'}</dd>
    </div>
    <div class="flex justify-between">
      <dt class="text-gray-400 text-xs">서버 IP</dt>
      <dd class="text-gray-300 font-mono text-xs">{s.cluster!.server_ip || '-'}</dd>
    </div>
    <div class="flex justify-between">
      <dt class="text-gray-400 text-xs">키페어</dt>
      <dd class="text-gray-300 text-xs">{s.cluster!.key_name || '-'}</dd>
    </div>
    {#if s.health}
      <div class="flex justify-between">
        <dt class="text-gray-400 text-xs">API 서버</dt>
        <dd class="text-xs {s.health.api_server_reachable ? 'text-green-400' : 'text-red-400'}">
          {s.health.api_server_reachable ? '접근 가능' : '접근 불가'}
        </dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-gray-400 text-xs">healthz</dt>
        <dd class="text-xs {s.health.healthz_ok ? 'text-green-400' : 'text-red-400'}">
          {s.health.healthz_ok ? 'OK' : 'FAIL'}
        </dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-gray-400 text-xs">체크 시각</dt>
        <dd class="text-gray-400 text-xs">{new Date(s.health.checked_at).toLocaleTimeString('ko-KR')}</dd>
      </div>
    {/if}
  </dl>
</div>
