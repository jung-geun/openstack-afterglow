<script lang="ts">
	import { betaFeatures, setBetaFeature } from '$lib/stores/betaFeatures';

	function toggleLibraryConsume(checked: boolean) {
		setBetaFeature('libraryConsume', checked);
	}

	function toggleHaDeploy(checked: boolean) {
		setBetaFeature('haDeploy', checked);
	}
</script>

<section class="bg-gray-900 border border-gray-800 rounded-xl p-5">
	<div class="mb-5">
		<p class="text-sm font-semibold text-white">고급 VM 생성 옵션</p>
		<p class="text-xs text-gray-400 mt-1">
			이 설정은 현재 브라우저에만 저장됩니다. 프로젝트 전체 서버 설정이나 다른 사용자에게는 적용되지 않습니다.
		</p>
	</div>

	<div class="space-y-4">
		<label class="flex items-start justify-between gap-4 rounded-lg border border-gray-800 bg-gray-950/40 px-4 py-3">
			<span>
				<span class="block text-sm font-medium text-gray-100">squashfs 라이브러리 소비 VM 생성 단계 표시</span>
				<span class="block text-xs text-gray-500 mt-1">Ubuntu 이미지 선택 시 VM 생성 마법사에서 관리자 공개 squashfs 프로필/레이어를 선택합니다.</span>
			</span>
			<input
				type="checkbox"
				class="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
				checked={$betaFeatures.libraryConsume}
				onchange={(event) => toggleLibraryConsume(event.currentTarget.checked)}
			/>
		</label>

		<label class="flex items-start justify-between gap-4 rounded-lg border border-gray-800 bg-gray-950/40 px-4 py-3">
			<span>
				<span class="block text-sm font-medium text-gray-100">HA 배포 옵션 표시</span>
				<span class="block text-xs text-gray-500 mt-1">VM 생성 전략 단계에서 HA 스케줄링 옵션을 노출합니다.</span>
			</span>
			<input
				type="checkbox"
				class="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
				checked={$betaFeatures.haDeploy}
				onchange={(event) => toggleHaDeploy(event.currentTarget.checked)}
			/>
		</label>
	</div>
</section>
