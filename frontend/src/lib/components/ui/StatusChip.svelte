<script lang="ts">
  import { getStatusColor } from '$lib/config/statusColors';

  interface Props {
    status: string | null | undefined;
    class?: string;
  }

  let { status, class: className = '' }: Props = $props();

  const c = $derived(getStatusColor(status));
</script>

<span
  class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border leading-tight {c.bg} {c.border} {c.text} {className}"
>
  <span class="w-1.5 h-1.5 rounded-full {c.dot}"></span>
  {status ?? '—'}
</span>
