<script lang="ts">
  interface Props {
    available: boolean;
    message: string | null;
  }
  let { available, message }: Props = $props();
</script>

{#if !available}
  <div class="bg-yellow-900/30 border border-yellow-700 text-yellow-300 rounded-lg px-4 py-3 text-sm mb-4">
    <span class="font-medium">Zun 서비스 미배포:</span> 이 환경에 Zun 컨테이너 서비스가 설치되어 있지 않습니다.
  </div>
{/if}
