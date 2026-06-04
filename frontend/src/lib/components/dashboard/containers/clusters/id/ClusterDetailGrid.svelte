<script lang="ts">
  import type { Cluster } from '$lib/types/cluster';
  import { clusterStatusColor } from '$lib/types/cluster';

  let { cluster }: { cluster: Cluster } = $props();
</script>

<div class="grid grid-cols-2 gap-4 mb-6">
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">상태</div>
    <span class="px-2 py-0.5 rounded text-xs font-medium {clusterStatusColor[cluster.status] ?? 'text-gray-400 bg-gray-800'}">{cluster.status}</span>
    {#if cluster.status_reason}
      <p class="text-xs text-gray-500 mt-2">{cluster.status_reason}</p>
    {/if}
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">노드 구성</div>
    <div class="text-white text-sm">마스터 {cluster.master_count}개 / 워커 {cluster.node_count}개</div>
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">API 주소</div>
    <div class="text-white text-xs font-mono">{cluster.api_address ?? '-'}</div>
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">COE 버전</div>
    <div class="text-white text-sm">{cluster.coe_version ?? '-'}</div>
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">키페어</div>
    <div class="text-white text-sm">{cluster.keypair ?? '-'}</div>
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">생성일</div>
    <div class="text-white text-sm">{cluster.created_at?.slice(0, 19).replace('T', ' ') ?? '-'}</div>
  </div>
</div>
{#if cluster.api_address}
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-3">kubectl 설정</div>
    <pre class="bg-gray-950 rounded p-3 text-xs text-green-300 overflow-auto">openstack coe cluster config {cluster.name} --dir ~/.kube --force</pre>
  </div>
{/if}
