<script lang="ts">
	import { page } from '$app/stores';
	import 'driver.js/dist/driver.css';
	import { isTourActive, readPersistedTour, startTour } from './engine';
	import { isTourId, tours, TOUR_QUERY_KEY } from './tours';

	let open = $state(false);
	let lastParam: string | null = null;
	let resumeChecked = false;

	$effect(() => {
		const param = $page.url.searchParams.get(TOUR_QUERY_KEY);
		if (param !== lastParam) {
			lastParam = param;
			if (param === 'intro') {
				open = true;
				return;
			}
			if (isTourId(param)) {
				open = false;
				void startTour(param);
				return;
			}
		}
		// 새로고침/재진입 시 진행 중이던 투어 재개 (이미 활성인 투어는 건드리지 않음)
		if (!resumeChecked) {
			resumeChecked = true;
			if (!param && !isTourActive()) {
				const persisted = readPersistedTour();
				if (persisted) void startTour(persisted.tourId, persisted.stepIndex);
			}
		}
	});

	function begin(tourId: (typeof tours)[number]['id']) {
		open = false;
		void startTour(tourId);
	}

	function close() {
		open = false;
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="launcher-overlay fixed inset-0 flex items-center justify-center z-[60] p-4"
		onclick={close}
		role="dialog"
		aria-modal="true"
		aria-label="튜토리얼 시작"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && close()}
	>
		<div
			class="launcher-card rounded-xl p-6 w-full max-w-lg shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="launcher-title text-lg font-semibold mb-1">튜토리얼</h2>
			<p class="launcher-lead text-sm mb-5">
				안내를 따라 핵심 기능을 직접 사용해 봅니다. 원하는 시나리오를 선택하세요.
			</p>
			<div class="space-y-2.5">
				{#each tours as tour (tour.id)}
					<button
						data-tour-launch={tour.id}
						onclick={() => begin(tour.id)}
						class="launcher-item w-full text-left rounded-lg px-4 py-3 transition-colors"
					>
						<div class="launcher-item-title text-sm font-medium">{tour.label}</div>
						<div class="launcher-item-summary text-xs mt-0.5">{tour.summary}</div>
					</button>
				{/each}
			</div>
			<div class="flex justify-end mt-5">
				<button
					onclick={close}
					class="launcher-dismiss px-4 py-2 text-sm transition-colors"
				>나중에 하기</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.launcher-overlay {
		background: color-mix(in oklab, var(--color-surface-base) 60%, transparent);
	}
	.launcher-card {
		background: var(--color-surface-raised);
		border: 1px solid var(--color-line);
	}
	.launcher-title {
		color: var(--color-ink-0);
	}
	.launcher-lead {
		color: var(--color-ink-2);
	}
	.launcher-item {
		background: var(--color-surface-sunken);
		border: 1px solid var(--color-line);
	}
	.launcher-item:hover {
		border-color: color-mix(in oklab, var(--color-line) 40%, var(--color-ink-2));
		background: color-mix(in oklab, var(--color-surface-sunken) 85%, var(--color-ink-0));
	}
	.launcher-item-title {
		color: var(--color-ink-0);
	}
	.launcher-item-summary {
		color: var(--color-ink-2);
	}
	.launcher-dismiss {
		color: var(--color-ink-2);
	}
	.launcher-dismiss:hover {
		color: var(--color-ink-0);
	}
</style>
