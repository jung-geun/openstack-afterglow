<script lang="ts">
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import ProfileSection from '$lib/components/account/ProfileSection.svelte';
  import PasswordSection from '$lib/components/account/PasswordSection.svelte';
  import ThemeSection from '$lib/components/account/ThemeSection.svelte';
  import GroupsSection from '$lib/components/account/GroupsSection.svelte';
  import ProjectsSection from '$lib/components/account/ProjectsSection.svelte';
  import KeypairsSection from '$lib/components/account/KeypairsSection.svelte';
</script>

<div class="p-4 md:p-8 max-w-5xl">
  <PageHeader breadcrumb="" title="계정 설정" />
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <ProfileSection />
    <PasswordSection />
    <ThemeSection />
    <ProjectsSection />
    <GroupsSection />
    <div class="lg:col-span-2">
      <KeypairsSection />
    </div>
  </div>
</div>
