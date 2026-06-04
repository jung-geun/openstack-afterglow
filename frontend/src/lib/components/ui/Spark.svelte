<script lang="ts">
  type Mode = 'fixedWidth' | 'stretch';

  interface Props {
    data: number[];
    mode?: Mode;
    width?: number;
    height?: number;
    color?: string;
    area?: boolean;
    class?: string;
  }

  let {
    data = [],
    mode = 'stretch',
    width = 80,
    height = 28,
    color = 'var(--color-accent)',
    area = true,
    class: className = '',
  }: Props = $props();

  const svgW = $derived(mode === 'fixedWidth' ? width : undefined);

  const path = $derived(() => {
    if (data.length < 2) return { line: '', fill: '' };
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const pts = data.map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return [x, y] as [number, number];
    });
    const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    const fill = `${line} L${pts[pts.length - 1][0].toFixed(1)},${height} L0,${height} Z`;
    return { line, fill };
  });
</script>

<svg
  viewBox="0 0 100 {height}"
  preserveAspectRatio="none"
  width={svgW}
  class="spark {className}"
  style="height:{height}px"
>
  {#if area && path().fill}
    <path
      d={path().fill}
      fill={color}
      opacity="0.12"
    />
  {/if}
  {#if path().line}
    <path
      d={path().line}
      fill="none"
      stroke={color}
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  {/if}
</svg>

<style>
  .spark {
    display: block;
    overflow: visible;
  }
</style>
