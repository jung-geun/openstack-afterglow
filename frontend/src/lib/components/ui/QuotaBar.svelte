<script lang="ts">
  interface Props {
    label: string;
    used: number;
    limit: number;
    color?: string;
  }

  let { label, used, limit, color = 'bg-blue-500' }: Props = $props();

  const pct = $derived(limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0);
</script>

<div>
  <div class="flex justify-between text-xs text-gray-400 mb-1.5">
    <span>{label}</span>
    <span><span class="text-white font-medium">{used}</span> / {limit}</span>
  </div>
  <div class="h-1 bg-gray-800 rounded-full overflow-hidden">
    <div class="{color} h-full rounded-full transition-all" style="width:{pct}%"></div>
  </div>
</div>
