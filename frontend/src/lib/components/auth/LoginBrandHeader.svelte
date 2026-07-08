<script lang="ts">
  import { onMount } from 'svelte';
  import { siteConfig } from '$lib/config/site';
  import { resolvedTheme } from '$lib/stores/theme';

  let themeReady = $state(false);

  onMount(() => {
    themeReady = true;
  });

  const resolvedLoginLogoSrc = $derived(
    $resolvedTheme === 'dark'
      ? ($siteConfig.logo_light_path || $siteConfig.logo_path)
      : ($siteConfig.logo_dark_path || $siteConfig.logo_path)
  );

  const loginLogoSrc = $derived(themeReady ? resolvedLoginLogoSrc : '');
</script>

<div class="text-center mb-8">
  <div class="h-24 sm:h-32 md:h-40 lg:h-48 mb-4 flex items-center justify-center">
    {#if loginLogoSrc}
      <img src={loginLogoSrc} alt={$siteConfig.site_name} class="h-full w-auto mx-auto" />
    {/if}
  </div>
  <h1 class="text-4xl font-bold text-white mb-2">{$siteConfig.site_name}</h1>
  <p class="text-gray-400 text-sm">{$siteConfig.site_description}</p>
</div>
