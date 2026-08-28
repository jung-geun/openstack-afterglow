<script lang="ts">
	import ToggleGroup from '$lib/components/ui/ToggleGroup.svelte';

	type ScenarioKey = 'gpu' | 'cluster' | 'data';

	type Scenario = {
		key: ScenarioKey;
		label: string;
		request: string;
		project: string;
		requestedAt: string;
		policy: Array<{ label: string; value: string }>;
		resource: Array<{ label: string; value: string }>;
		outputLabel: string;
		output: string;
	};

	const scenarios: Scenario[] = [
		{
			key: 'gpu',
			label: 'GPU 연구',
			request: '멀티모달 학습 환경',
			project: 'lab-vision · 연구원 2명',
			requestedAt: '09:41',
			policy: [
				{ label: '프로젝트 쿼터', value: '범위 내' },
				{ label: 'GPU 정책', value: '승인' },
				{ label: '네트워크', value: '격리됨' },
			],
			resource: [
				{ label: 'GPU VM', value: '1' },
				{ label: 'vCPU', value: '16' },
				{ label: '메모리', value: '64 GB' },
			],
			outputLabel: '재사용 레이어',
			output: 'pytorch-vision-lab',
		},
		{
			key: 'cluster',
			label: '클러스터 실습',
			request: '분산 학습 실습 환경',
			project: 'course-dl · 실습팀 24명',
			requestedAt: '10:12',
			policy: [
				{ label: '노드 쿼터', value: '범위 내' },
				{ label: '수업 기간', value: '14일' },
				{ label: '접근 역할', value: '분리됨' },
			],
			resource: [
				{ label: 'K8s 노드', value: '3' },
				{ label: 'vCPU', value: '24' },
				{ label: '메모리', value: '96 GB' },
			],
			outputLabel: '다음 수업 템플릿',
			output: 'distributed-training',
		},
		{
			key: 'data',
			label: '공유 데이터',
			request: '팀 데이터셋 분석 공간',
			project: 'lab-genomics · 연구원 7명',
			requestedAt: '11:08',
			policy: [
				{ label: '공유 범위', value: '프로젝트' },
				{ label: '접근 규칙', value: '승인' },
				{ label: '보존 정책', value: '30일' },
			],
			resource: [
				{ label: '파일 공간', value: '2 TB' },
				{ label: '접근 규칙', value: '3' },
				{ label: '스냅샷', value: '매일' },
			],
			outputLabel: '공유 스냅샷',
			output: 'genomics-baseline',
		},
	];

	const scenarioOptions = scenarios.map(({ key, label }) => ({ value: key, label }));
	let selectedScenario = $state<ScenarioKey>('gpu');
	let activeScenario = $derived(
		scenarios.find((scenario) => scenario.key === selectedScenario) ?? scenarios[0]!,
	);

	function selectScenario(value: string) {
		if (value === 'gpu' || value === 'cluster' || value === 'data') selectedScenario = value;
	}
</script>

<section class="ops-board" data-scenario={selectedScenario} aria-labelledby="ops-board-title">
	<header class="board-header">
		<div>
			<span class="board-kicker">Delivery map</span>
			<h2 id="ops-board-title">연구 환경 제공 현황</h2>
		</div>
		<div class="board-health"><span aria-hidden="true"></span>모든 제어면 정상</div>
	</header>

	<ToggleGroup
		value={selectedScenario}
		options={scenarioOptions}
		onchange={selectScenario}
		size="sm"
		fullWidth
		class="scenario-switcher"
		ariaLabel="연구 운영 시나리오"
	/>

	<div class="board-flow" aria-live="polite">
		<article class="flow-card request-card">
			<div class="flow-meta"><span>Request</span><time>{activeScenario.requestedAt}</time></div>
			<h3>{activeScenario.request}</h3>
			<p>{activeScenario.project}</p>
			<div class="request-state"><span aria-hidden="true"></span>배정 준비됨</div>
		</article>

		<div class="flow-rail" aria-hidden="true">
			<span></span>
			<b>정책 확인</b>
		</div>

		<article class="flow-card policy-card">
			<div class="flow-meta"><span>Policy gate</span><span>3 / 3</span></div>
			<ul>
				{#each activeScenario.policy as check}
					<li><span>{check.label}</span><strong><i aria-hidden="true">✓</i>{check.value}</strong></li>
				{/each}
			</ul>
		</article>

		<div class="flow-rail" aria-hidden="true">
			<span></span>
			<b>즉시 제공</b>
		</div>

		<div class="delivery-stack">
			<article class="flow-card resource-card">
				<div class="flow-meta"><span>Allocated</span><span class="live-label">Live</span></div>
				<div class="resource-grid">
					{#each activeScenario.resource as resource}
						<div><span>{resource.label}</span><strong>{resource.value}</strong></div>
					{/each}
				</div>
			</article>
			<article class="output-card">
				<div class="output-icon" aria-hidden="true"><span></span><span></span><span></span></div>
				<div><span>{activeScenario.outputLabel}</span><strong>{activeScenario.output}</strong></div>
				<b>ready</b>
			</article>
		</div>
	</div>

	<footer class="board-footer">
		<span>신청</span><i aria-hidden="true"></i><span>배정</span><i aria-hidden="true"></i><span>관측</span><i aria-hidden="true"></i><strong>재사용</strong>
	</footer>
</section>

<style>
	.ops-board {
		position: relative;
		isolation: isolate;
		overflow: hidden;
		border: 1px solid var(--color-line-2);
		border-radius: 1.25rem;
		background: color-mix(in oklab, var(--color-surface-base) 94%, transparent);
		box-shadow: 0 2rem 5rem color-mix(in oklab, var(--color-surface-canvas) 70%, transparent);
	}

	.ops-board::before {
		content: '';
		position: absolute;
		inset: 0;
		z-index: -1;
		background-image: var(--pattern-editorial-grid);
		background-size: 2.75rem 2.75rem;
		opacity: 0.18;
		mask-image: linear-gradient(to bottom, black, transparent 72%);
	}

	.board-header,
	.board-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.125rem;
	}

	.board-header { border-bottom: 1px solid var(--color-line); }
	.board-kicker,
	.flow-meta,
	.board-footer,
	.request-state,
	.output-card > b {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		letter-spacing: 0.07em;
		text-transform: uppercase;
	}

	.board-kicker { color: var(--color-warm-text); }
	.board-header h2 { margin: 0.125rem 0 0; font-size: 1rem; line-height: 1.25; }
	.board-health { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--color-ink-2); font-size: 0.75rem; }
	.board-health > span,
	.request-state > span {
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 999px;
		background: var(--color-state-success);
		box-shadow: 0 0 0 0.25rem color-mix(in oklab, var(--color-state-success) 14%, transparent);
	}

	:global(.scenario-switcher) {
		margin: 1rem 1.125rem 0;
		width: calc(100% - 2.25rem);
		background: color-mix(in oklab, var(--color-surface-sunken) 78%, transparent);
	}

	:global(.scenario-switcher .toggle-option) { min-height: 2.75rem; }
	:global(.scenario-switcher .toggle-selected) { color: var(--color-ink-0); box-shadow: inset 0 -2px 0 var(--color-warm); }

	.board-flow { display: grid; padding: 1.125rem; }
	.flow-card {
		border: 1px solid var(--color-line);
		border-radius: 0.875rem;
		background: color-mix(in oklab, var(--color-surface-raised) 92%, transparent);
	}

	.request-card,
	.policy-card,
	.resource-card { padding: 1rem; }
	.flow-meta { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; color: var(--color-ink-2); }
	.flow-meta > span:first-child { color: var(--color-accent); }
	.request-card h3 { margin: 1.75rem 0 0; font-size: 1.375rem; line-height: 1.12; word-break: keep-all; }
	.request-card p { margin: 0.5rem 0 0; color: var(--color-ink-2); font-size: 0.75rem; }
	.request-state { display: inline-flex; align-items: center; gap: 0.5rem; margin-top: 1.5rem; color: var(--color-state-success-text); }

	.flow-rail { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 0.625rem; min-height: 2.75rem; color: var(--color-ink-2); }
	.flow-rail::before,
	.flow-rail::after { content: ''; border-top: 1px dashed var(--color-line-2); }
	.flow-rail span { display: none; }
	.flow-rail b { font-family: var(--font-mono); font-size: 0.625rem; font-weight: 500; letter-spacing: 0.06em; }

	.policy-card ul { display: grid; gap: 0.75rem; margin: 1rem 0 0; padding: 0; list-style: none; }
	.policy-card li { display: flex; align-items: center; justify-content: space-between; gap: 1rem; color: var(--color-ink-2); font-size: 0.75rem; }
	.policy-card li strong { display: inline-flex; align-items: center; gap: 0.375rem; color: var(--color-ink-1); font-weight: 600; }
	.policy-card li i { display: grid; place-items: center; width: 1rem; height: 1rem; border-radius: 999px; background: color-mix(in oklab, var(--color-state-success) 14%, transparent); color: var(--color-state-success-text); font-size: 0.625rem; font-style: normal; }

	.delivery-stack { display: grid; gap: 0.625rem; }
	.live-label { color: var(--color-state-success-text); }
	.resource-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; margin-top: 1rem; }
	.resource-grid > div { min-width: 0; padding: 0.75rem; border-radius: 0.625rem; background: var(--color-surface-sunken); }
	.resource-grid span,
	.output-card span { display: block; color: var(--color-ink-2); font-size: 0.6875rem; }
	.resource-grid strong { display: block; margin-top: 0.35rem; font-size: 1rem; overflow-wrap: anywhere; }

	.output-card { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 0.75rem; padding: 0.75rem; border: 1px solid color-mix(in oklab, var(--color-warm) 35%, var(--color-line)); border-radius: 0.875rem; background: color-mix(in oklab, var(--color-warm) 7%, var(--color-surface-raised)); }
	.output-card strong { display: block; margin-top: 0.125rem; overflow: hidden; font-size: 0.75rem; text-overflow: ellipsis; white-space: nowrap; }
	.output-card > b { color: var(--color-warm-text); font-weight: 600; }
	.output-icon { display: grid; width: 2.25rem; gap: 0.1875rem; }
	.output-icon span { height: 0.35rem; border: 1px solid var(--color-warm); border-radius: 0.1875rem; background: color-mix(in oklab, var(--color-warm) 10%, transparent); }
	.output-icon span:nth-child(2) { margin-inline: 0.2rem; opacity: 0.72; }
	.output-icon span:nth-child(3) { margin-inline: 0.4rem; opacity: 0.45; }

	.board-footer { justify-content: center; border-top: 1px solid var(--color-line); color: var(--color-ink-2); }
	.board-footer i { width: 1.5rem; border-top: 1px solid var(--color-line-2); }
	.board-footer strong { color: var(--color-warm-text); }

	@media (min-width: 768px) {
		.board-flow { grid-template-columns: minmax(0, 0.92fr) 2.75rem minmax(0, 1fr); align-items: stretch; }
		.request-card { grid-row: span 1; }
		.flow-rail { grid-template-columns: 1fr; grid-template-rows: 1fr auto 1fr; min-height: 0; padding: 0.5rem 0; justify-items: center; }
		.flow-rail::before,
		.flow-rail::after { align-self: stretch; border-top: 0; border-left: 1px dashed var(--color-line-2); }
		.flow-rail b { writing-mode: vertical-rl; }
		.policy-card { grid-column: 3; }
		.board-flow > .flow-rail:nth-of-type(2) { display: none; }
		.delivery-stack { grid-column: 1 / -1; grid-template-columns: minmax(0, 1fr) minmax(14rem, 0.72fr); margin-top: 0.75rem; }
	}

	@media (min-width: 1024px) {
		.request-card h3 { margin-top: 2rem; }
	}

	@media (min-width: 1280px) {
		.board-flow { grid-template-columns: minmax(0, 0.86fr) 2.75rem minmax(0, 0.9fr) 2.75rem minmax(0, 1.1fr); }
		.request-card,
		.policy-card,
		.delivery-stack { grid-column: auto; }
		.board-flow > .flow-rail:nth-of-type(2) { display: grid; }
		.delivery-stack { grid-template-columns: 1fr; margin-top: 0; }
		.request-card h3 { margin-top: 2.5rem; }
	}

	@media (prefers-reduced-motion: reduce) {
		.ops-board,
		.ops-board :global(*) { scroll-behavior: auto; transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
	}
</style>
