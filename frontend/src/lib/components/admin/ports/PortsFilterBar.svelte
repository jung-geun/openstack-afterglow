<script lang="ts">
  let {
    search = $bindable(),
    projectFilter = $bindable(),
    projectOptions,
    onProjectChange,
  }: {
    search: string;
    projectFilter: string;
    projectOptions: { id: string; name: string }[];
    onProjectChange: () => void;
  } = $props();
</script>

<div class="flex flex-wrap gap-3 mb-4">
  <input
    type="text"
    bind:value={search}
    placeholder="필터 (이름, device_owner, IP)"
    class="text-xs bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-gray-300 placeholder-gray-600 w-56"
  />
  <select
    bind:value={projectFilter}
    onchange={onProjectChange}
    class="text-xs bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-gray-300 focus:outline-none focus:border-blue-500"
  >
    <option value="">전체 프로젝트</option>
    {#each projectOptions as p (p.id)}
      <option value={p.id}>{p.name}</option>
    {/each}
  </select>
</div>
