<script lang="ts">
  import { goto } from '$app/navigation';
  import { palette } from '$lib/stores/palette';
  import { auth } from '$lib/stores/auth';
  import { api } from '$lib/api/client';
  import { allNavItems } from '$lib/config/nav';
  import { isAdmin } from '$lib/stores/auth';

  interface PaletteItem {
    id: string;
    label: string;
    sublabel?: string;
    type: 'route' | 'instance' | 'volume' | 'image' | 'network' | 'router';
    href: string;
    icon?: string;
  }

  let query = $state('');
  let selectedIdx = $state(0);
  let inputEl = $state<HTMLInputElement | null>(null);
  let indexedAt = $state(0);
  let resourceItems = $state<PaletteItem[]>([]);

  const ICONS: Record<PaletteItem['type'], string> = {
    route: 'M4 6h16M4 12h16M4 18h7',
    instance: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2',
    volume: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7',
    image: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14',
    network: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3',
    router: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  };

  const navItems: PaletteItem[] = allNavItems($isAdmin).map((item) => ({
    id: `route:${item.href}`,
    label: item.label,
    sublabel: item.section,
    type: 'route',
    href: item.href,
    icon: ICONS.route,
  }));

  async function loadResources() {
    const now = Date.now();
    if (now - indexedAt < 60_000) return;
    indexedAt = now;
    const token = $auth.token ?? undefined;
    const project = $auth.projectId ?? undefined;

    try {
      const results = await Promise.allSettled([
        api.get<Array<{ id: string; name?: string }>>('/api/instances', token, project),
        api.get<Array<{ id: string; name?: string }>>('/api/volumes', token, project),
        api.get<Array<{ id: string; name?: string }>>('/api/images', token, project),
        api.get<Array<{ id: string; name?: string }>>('/api/networks', token, project),
        api.get<Array<{ id: string; name?: string }>>('/api/routers', token, project),
      ]);

      const [instances, volumes, images, networks, routers] = results;
      const items: PaletteItem[] = [];

      if (instances.status === 'fulfilled') {
        for (const r of instances.value ?? []) {
          items.push({ id: r.id, label: r.name || r.id.slice(0, 12), sublabel: '인스턴스', type: 'instance', href: `/dashboard/compute/instances/${r.id}`, icon: ICONS.instance });
        }
      }
      if (volumes.status === 'fulfilled') {
        for (const r of (volumes.value as Array<{ id: string; name?: string }> | null) ?? []) {
          items.push({ id: r.id, label: r.name || r.id.slice(0, 12), sublabel: '볼륨', type: 'volume', href: `/dashboard/volumes/${r.id}`, icon: ICONS.volume });
        }
      }
      if (images.status === 'fulfilled') {
        for (const r of (images.value as Array<{ id: string; name?: string }> | null) ?? []) {
          items.push({ id: r.id, label: r.name || r.id.slice(0, 12), sublabel: '이미지', type: 'image', href: `/dashboard/compute/images`, icon: ICONS.image });
        }
      }
      if (networks.status === 'fulfilled') {
        for (const r of (networks.value as Array<{ id: string; name?: string }> | null) ?? []) {
          items.push({ id: r.id, label: r.name || r.id.slice(0, 12), sublabel: '네트워크', type: 'network', href: `/dashboard/network/networks`, icon: ICONS.network });
        }
      }
      if (routers.status === 'fulfilled') {
        for (const r of (routers.value as Array<{ id: string; name?: string }> | null) ?? []) {
          items.push({ id: r.id, label: r.name || r.id.slice(0, 12), sublabel: '라우터', type: 'router', href: `/dashboard/network/routers`, icon: ICONS.router });
        }
      }
      resourceItems = items;
    } catch {
      // index load failure is non-fatal
    }
  }

  function fuzzyMatch(needle: string, haystack: string): boolean {
    if (!needle) return true;
    const n = needle.toLowerCase();
    const h = haystack.toLowerCase();
    let ni = 0;
    for (let i = 0; i < h.length && ni < n.length; i++) {
      if (h[i] === n[ni]) ni++;
    }
    return ni === n.length;
  }

  const results = $derived.by(() => {
    const q = query.trim();
    const all = [...navItems, ...resourceItems];
    if (!q) return navItems.slice(0, 8);
    return all.filter((item) => fuzzyMatch(q, item.label) || fuzzyMatch(q, item.sublabel ?? '')).slice(0, 12);
  });

  $effect(() => {
    selectedIdx = 0;
  });

  $effect(() => {
    if ($palette) {
      query = '';
      setTimeout(() => inputEl?.focus(), 10);
      loadResources();
    }
  });

  function navigate(href: string) {
    palette.close();
    goto(href);
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIdx = Math.min(selectedIdx + 1, results.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIdx = Math.max(selectedIdx - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = results[selectedIdx];
      if (item) navigate(item.href);
    } else if (e.key === 'Escape') {
      palette.close();
    }
  }
</script>

{#if $palette}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[200]"
    onclick={() => palette.close()}
    role="presentation"
  ></div>

  <!-- Panel -->
  <div
    class="fixed top-[20vh] left-1/2 -translate-x-1/2 w-full max-w-xl z-[201] px-4"
    role="dialog"
    aria-modal="true"
    aria-label="커맨드 팔레트"
  >
    <div class="palette-panel rounded-2xl border border-line-2 shadow-2xl overflow-hidden">
      <!-- Input -->
      <div class="flex items-center gap-3 px-4 py-3 border-b border-line">
        <svg class="w-4 h-4 text-ink-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/>
        </svg>
        <input
          bind:this={inputEl}
          bind:value={query}
          onkeydown={onKeydown}
          type="text"
          placeholder="메뉴 또는 리소스 검색..."
          autocomplete="off"
          class="flex-1 bg-transparent text-[14px] text-ink-0 placeholder-ink-3 outline-none"
        />
        <kbd class="text-[10px] text-ink-3 border border-line px-1.5 py-0.5 rounded font-mono">ESC</kbd>
      </div>

      <!-- Results -->
      {#if results.length > 0}
        <ul class="max-h-80 overflow-y-auto py-1">
          {#each results as item, i}
            <li>
              <button
                onclick={() => navigate(item.href)}
                class="palette-item w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                class:palette-item-selected={i === selectedIdx}
                onmouseenter={() => selectedIdx = i}
              >
                <span class="palette-icon w-7 h-7 rounded-lg flex items-center justify-center shrink-0">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={item.icon ?? ICONS.route}/>
                  </svg>
                </span>
                <div class="min-w-0 flex-1">
                  <div class="text-[13px] font-medium text-ink-0 truncate">{item.label}</div>
                  {#if item.sublabel}
                    <div class="text-[11px] text-ink-3 truncate">{item.sublabel}</div>
                  {/if}
                </div>
                <kbd class="text-[10px] text-ink-3 opacity-0 group-hover:opacity-100">↵</kbd>
              </button>
            </li>
          {/each}
        </ul>
      {:else}
        <div class="px-4 py-6 text-center text-sm text-ink-3">결과 없음</div>
      {/if}
    </div>
  </div>
{/if}

<svelte:window
  onkeydown={(e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if ($palette) palette.close(); else palette.open();
    }
  }}
/>

<style>
  .palette-panel {
    background: var(--color-surface-raised);
  }
  .palette-item:hover,
  .palette-item-selected {
    background: var(--color-surface-sunken);
  }
  .palette-icon {
    background: color-mix(in oklab, var(--color-accent) 12%, transparent);
    color: var(--color-accent);
  }
  .palette-item-selected .palette-icon {
    background: color-mix(in oklab, var(--color-warm) 14%, transparent);
    color: var(--color-warm);
  }
</style>
