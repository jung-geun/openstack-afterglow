<script lang="ts">
  import type { TemplateInfo } from '$lib/types/templates';

  let {
    templates,
    refreshing,
    onSelect,
  }: {
    templates: TemplateInfo[];
    refreshing: boolean;
    onSelect: (t: TemplateInfo) => void;
  } = $props();

  function formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  }
</script>

  <div class="rounded-lg border border-gray-700 overflow-hidden overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="bg-gray-800 text-gray-400 text-xs uppercase">
        <tr>
          <th class="px-4 py-3 text-left">이름</th>
          <th class="px-4 py-3 text-left">버전</th>
          <th class="px-4 py-3 text-left hidden md:table-cell">Ubuntu Base</th>
          <th class="px-4 py-3 text-left hidden lg:table-cell">설명</th>
          <th class="px-4 py-3 text-left hidden lg:table-cell">생성일</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-700/50">
        {#each templates as tmpl}
          <tr
            class="hover:bg-gray-800/50 cursor-pointer transition-colors"
            onclick={() => onSelect(tmpl)}
          >
            <td class="px-4 py-3 font-medium"><span class="max-md:block max-md:max-w-[66vw] max-md:truncate" title={tmpl.name}>{tmpl.name}</span></td>
            <td class="px-4 py-3 text-gray-400">v{tmpl.version}</td>
            <td class="px-4 py-3 hidden md:table-cell text-gray-400 text-xs">{tmpl.ubuntu_base}</td>
            <td class="px-4 py-3 hidden lg:table-cell text-gray-500 text-xs">{tmpl.note ?? '-'}</td>
            <td class="px-4 py-3 hidden lg:table-cell text-gray-500 text-xs">{formatDate(tmpl.created_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
