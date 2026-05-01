<script lang="ts">
  import { theme, type ThemePreference } from '$lib/stores/theme';

  const options: { value: ThemePreference; label: string; desc: string }[] = [
    { value: 'system', label: '시스템', desc: 'OS 설정에 따라 자동 전환' },
    { value: 'dark', label: '다크', desc: '항상 어두운 테마' },
    { value: 'light', label: '라이트', desc: '항상 밝은 테마' },
  ];
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
  <h3 class="text-sm font-semibold text-white mb-4">화면 테마</h3>
  <div class="grid grid-cols-3 gap-2">
    {#each options as opt}
      <button
        onclick={() => theme.set(opt.value)}
        class="flex flex-col items-center gap-1.5 p-3 rounded-lg border transition-colors text-center
          {$theme === opt.value
            ? 'border-blue-500 bg-blue-500/10 text-blue-300'
            : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600 hover:text-gray-300'}"
      >
        <span class="text-xs font-medium">{opt.label}</span>
        <span class="text-[10px] text-gray-500 leading-tight">{opt.desc}</span>
      </button>
    {/each}
  </div>
</div>
