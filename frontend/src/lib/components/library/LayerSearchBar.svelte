<script lang="ts">
  let {
    query = $bindable(),
    onSearch,
  }: {
    query: string;
    onSearch: () => void;
  } = $props();
</script>

<div class="mb-4 flex gap-2">
  <input
    type="text"
    bind:value={query}
    placeholder="이름으로 검색..."
    class="flex-1 max-w-xs px-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded-md focus:outline-none focus:border-blue-500"
    onkeydown={(e) => e.key === 'Enter' && onSearch()}
  />
  <button
    onclick={onSearch}
    class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
  >검색</button>
  {#if query}
    <button
      onclick={() => { query = ''; onSearch(); }}
      class="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200"
    >초기화</button>
  {/if}
</div>
