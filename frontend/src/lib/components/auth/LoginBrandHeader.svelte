<script lang="ts">
  import { siteConfig } from '$lib/config/site';
  import { resolvedTheme } from '$lib/stores/theme';
</script>

<div class="text-center mb-8">
  <img
    src={$resolvedTheme === 'light' ? $siteConfig.logo_light_path : $siteConfig.logo_dark_path}
    alt={$siteConfig.site_name}
    class="h-24 sm:h-32 md:h-40 lg:h-48 w-auto mx-auto mb-4"
  />
  <h1 class="text-4xl font-bold text-white mb-2">{$siteConfig.site_name}</h1>
  <p class="text-gray-400 text-sm">{$siteConfig.site_description}</p>
</div>
