<script lang="ts">
	import { onMount } from 'svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ToggleGroup from '$lib/components/ui/ToggleGroup.svelte';
	import LandingFigure from './LandingFigure.svelte';

	interface Props {
		siteName: string;
		logoPath: string;
		consoleHref: string;
	}

	let { siteName, logoPath, consoleHref }: Props = $props();

	const navLinks = [
		{ label: '개요', href: '#overview' },
		{ label: '제공 기능', href: '#capabilities' },
		{ label: '워크플로우', href: '#workflow' },
		{ label: '화면', href: '#work' },
		{ label: '문의', href: '#contact' },
	];

	const overviewRows = [
		{ num: '01', title: '신청', body: '연구원이 필요한 실험 환경을 프로젝트 범위 안에서 요청합니다.' },
		{ num: '02', title: '배정', body: '관리자는 VM, 스토리지, 네트워크, 클러스터 자원을 정책에 맞게 제공합니다.' },
		{ num: '03', title: '관측', body: '사용량과 상태를 지표, 로그, 토폴로지로 확인합니다.' },
		{ num: '04', title: '재사용', body: '라이브러리 레이어와 스냅샷으로 다음 연구자의 환경 준비 시간을 줄입니다.' },
	];

	const capabilities = [
		{
			num: '01',
			tag: 'Compute',
			src: '/landing/plate-compute-allocation.svg',
			alt: 'VM 서버, GPU 칩, vCPU, 스토리지 자원 배정 콜라주',
			title: 'VM·GPU·vCPU·스토리지 자원 배정',
			body: 'GPU 가속 VM에 필요한 GPU, vCPU, 메모리, 스토리지를 프로젝트 쿼터 안에서 배정해 개별 실험 환경을 바로 준비합니다.',
		},
		{
			num: '02',
			tag: 'Cluster',
			src: '/landing/plate-kubernetes.svg',
			alt: 'K8s 클러스터 프로비저닝 콜라주',
			title: 'Kubernetes 실습과 실험 환경',
			body: 'K8s 클러스터 노드를 구성한 뒤 수업·연구 프로젝트의 Pod와 워크로드를 배포하고 상태를 콘솔에서 추적합니다.',
		},
		{
			num: '03',
			tag: 'Library',
			src: '/landing/plate-layer.svg',
			alt: 'AI ML 라이브러리 레이어 콜라주',
			title: 'AI/ML 라이브러리 레이어',
			body: '반복 설치가 필요한 프레임워크와 데이터 처리 도구를 불변 레이어로 관리해 팀별 환경을 재사용하고 포크합니다.',
		},
		{
			num: '04',
			tag: 'Governance',
			src: '/landing/plate-security.svg',
			alt: '보안과 거버넌스 콜라주',
			title: '교수자와 관리자용 운영 제어',
			body: '프로젝트, 사용자, 역할, 쿼터, 모니터링, 감사 로그를 묶어 연구실 단위 운영 기준을 유지합니다.',
		},
	];

	type WorkflowKind = 'compute' | 'data' | 'ops';
	type WorkflowFilter = 'all' | WorkflowKind;

	const filters = [
		{ label: '전체', value: 'all' },
		{ label: '컴퓨팅', value: 'compute' },
		{ label: '데이터', value: 'data' },
		{ label: '운영', value: 'ops' },
	];

	const workflowCards: Array<{
		kind: WorkflowKind;
		src: string;
		alt: string;
		title: string;
		body: string;
	}> = [
		{
			kind: 'compute',
			src: '/landing/plate-api.svg',
			alt: 'API 자동화 콜라주',
			title: '컴퓨팅 자원 신청',
			body: '연구원이 필요한 이미지, flavor, 네트워크, 키를 선택해 실험 인스턴스를 준비합니다.',
		},
		{
			kind: 'data',
			src: '/landing/plate-shared-data.svg',
			alt: '공유 데이터 공간과 스냅샷 흐름 콜라주',
			title: '공유 데이터 공간',
			body: '파일 스토리지와 스냅샷으로 팀 데이터와 실험 산출물을 안전하게 이어갑니다.',
		},
		{
			kind: 'compute',
			src: '/landing/plate-kubernetes.svg',
			alt: 'K8s 클러스터 프로비저닝 콜라주',
			title: '클러스터 실습',
			body: '수업이나 프로젝트별 Kubernetes 클러스터를 만들고 노드 구성을 추적합니다.',
		},
		{
			kind: 'ops',
			src: '/landing/plate-monitoring.svg',
			alt: '모니터링과 관측성 콜라주',
			title: '관측 가능한 운영',
			body: '지표 기반 화면을 통해 사용량과 병목을 빠르게 확인합니다.',
		},
		{
			kind: 'ops',
			src: '/landing/plate-release.svg',
			alt: '클라우드 배포 흐름 콜라주',
			title: '보안과 감사',
			body: '권한 경계, 키 분리 암호화, 작업 로그로 멀티테넌트 위험을 줄입니다.',
		},
	];

	type MethodStep = {
		step: string;
		title: string;
		alt: string;
		src?: string;
		icon?: 'observability' | 'reuse';
	};

	const methodSteps: MethodStep[] = [
		{ step: 'STEP 01', title: '연구 목적에 맞는 프로젝트를 만든다', src: '/landing/plate-professor.svg', alt: '연구팀별 클라우드 제공 콜라주' },
		{ step: 'STEP 02', title: '컴퓨팅과 데이터 자원을 배정한다', src: '/landing/plate-quota.svg', alt: '쿼터와 자원 배분 콜라주' },
		{ step: 'STEP 03', title: '실험 환경을 실행하고 관측한다', icon: 'observability', alt: '실험 실행, 지표, 로그 관측 아이콘' },
		{ step: 'STEP 04', title: '레이어와 스냅샷으로 다시 쓴다', icon: 'reuse', alt: '레이어와 스냅샷 재사용 아이콘' },
	];

	const email = 'pieroot@konkuk.ac.kr';
	const sectionIds = ['overview', 'capabilities', 'workflow', 'work', 'contact'];

	let landingRoot: HTMLElement;
	let selectedFilter: WorkflowFilter = $state('all');
	let activeSection = $state('overview');
	let navLinksElement: HTMLDivElement;
	let progressWidth = $derived(
		selectedFilter === 'all' ? '25%' : selectedFilter === 'compute' ? '50%' : selectedFilter === 'data' ? '75%' : '100%',
	);
	let visibleCount = $derived(
		workflowCards.filter((card) => selectedFilter === 'all' || card.kind === selectedFilter).length,
	);

	let revealObserver: IntersectionObserver | undefined;
	let revealReadyFrame: number | undefined;

	$effect(() => {
		if (!navLinksElement) return;
		const activeLink = navLinksElement.querySelector<HTMLAnchorElement>(`a[href="#${activeSection}"]`);
		if (!activeLink) return;
		const linkRect = activeLink.getBoundingClientRect();
		const navRect = navLinksElement.getBoundingClientRect();
		navLinksElement.scrollLeft = Math.max(0, navLinksElement.scrollLeft + linkRect.left - navRect.left - (navLinksElement.clientWidth - linkRect.width) / 2);
	});

	function isWorkflowFilter(value: string): value is WorkflowFilter {
		return value === 'all' || value === 'compute' || value === 'data' || value === 'ops';
	}

	function selectFilter(value: string) {
		if (isWorkflowFilter(value)) selectedFilter = value;
	}

	function focusLandingContent() {
		document.getElementById('landing-content')?.focus();
	}

	function updateActiveSection() {
		const activationLine = 148;
		let current = 'overview';
		for (const id of sectionIds) {
			const section = document.getElementById(id);
			if (section && section.getBoundingClientRect().top <= activationLine) current = id;
		}
		activeSection = current;
	}

	onMount(() => {
		const html = document.documentElement;
		const previousScrollBehavior = html.style.scrollBehavior;
		const reducedMotion = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		html.style.scrollBehavior = reducedMotion ? 'auto' : 'smooth';

		const handleScroll = () => updateActiveSection();
		updateActiveSection();
		window.addEventListener('scroll', handleScroll, { passive: true });

		const revealItems = Array.from(landingRoot.querySelectorAll<HTMLElement>('[data-reveal]'));
		if (!reducedMotion && typeof window.IntersectionObserver === 'function') {
			landingRoot.classList.add('reveal-enabled');
			revealObserver = new window.IntersectionObserver(
				(entries) => {
					for (const entry of entries) {
						if (entry.isIntersecting) {
							entry.target.classList.add('is-visible');
							revealObserver?.unobserve(entry.target);
						}
					}
				},
				{ threshold: 0.18, rootMargin: '0px 0px -8% 0px' },
			);
			revealItems.forEach((item) => revealObserver?.observe(item));
			revealReadyFrame = window.requestAnimationFrame(() => {
				landingRoot.classList.add('reveal-ready');
			});
		}

		return () => {
			window.removeEventListener('scroll', handleScroll);
			revealObserver?.disconnect();
			revealObserver = undefined;
			if (revealReadyFrame !== undefined) window.cancelAnimationFrame(revealReadyFrame);
			revealReadyFrame = undefined;
			landingRoot.classList.remove('reveal-enabled', 'reveal-ready');
			html.style.scrollBehavior = previousScrollBehavior;
		};
	});
</script>

<div class="landing-page" bind:this={landingRoot}>
	<a class="skip-link" href="#landing-content" onclick={focusLandingContent}>본문으로 건너뛰기</a>

	<header class="top-strip">
		<nav class="container nav" aria-label="주요 내비게이션">
			<a class="brand" href="/">
				<img src={logoPath} alt="" />
				<span>{siteName}</span>
			</a>
			<div class="nav-links" bind:this={navLinksElement}>
				{#each navLinks as link}
					<a
						href={link.href}
						class:is-active={activeSection === link.href.slice(1)}
						aria-current={activeSection === link.href.slice(1) ? 'location' : undefined}
					>{link.label}</a>
				{/each}
			</div>
			<Button variant="primary" size="md" class="nav-cta" href={consoleHref}>콘솔 접속</Button>
		</nav>
	</header>

	<div id="landing-content" tabindex="-1">
		<section class="hero">
			<div class="container hero-grid">
				<div data-reveal>
					<span class="eyebrow">I / Research cloud delivery console</span>
					<h1 class="dot">연구실 클라우드를 더 쉽게 제공하는 <span class="em">운영 콘솔</span></h1>
					<p class="lead">Afterglow는 교수, 연구원, 실습팀이 필요한 컴퓨팅 자원과 공유 스토리지, Kubernetes 환경, AI/ML 라이브러리 레이어를 한 곳에서 신청하고 운영하도록 설계된 클라우드 포털입니다.</p>
					<div class="hero-actions">
						<Button variant="primary" size="lg" class="landing-btn" href={consoleHref}>콘솔 접속</Button>
						<Button variant="outline" size="lg" class="landing-btn" href="/dashboard?tutorial=on">튜토리얼 체험</Button>
						<Button variant="outline" size="lg" class="landing-btn" href="#capabilities">기능 보기</Button>
					</div>
					<div class="stat-rings">
						<div class="ring"><strong>VM</strong><span>연구용 인스턴스 배정</span></div>
						<div class="ring"><strong>K8s</strong><span>클러스터 제공과 상태 추적</span></div>
						<div class="ring"><strong>Layer</strong><span>AI/ML 환경 재사용</span></div>
					</div>
				</div>
				<div class="collage" data-reveal>
					<LandingFigure class="plate hero-main" src="/landing/plate-lab-cloud.svg" alt="연구실 클라우드 콜라주" lazy={false} />
					<LandingFigure class="plate hero-side" src="/landing/plate-quota.svg" alt="쿼터와 자원 배분 콜라주" lazy={false} />
					<LandingFigure class="plate hero-wide" src="/landing/plate-console.svg" alt="Afterglow 프로젝트 대시보드 화면" lazy={false} />
				</div>
			</div>
		</section>

		<section id="overview" class="section">
			<div class="container">
				<div class="section-kicker" data-reveal>
					<span class="roman">II</span>
					<div>
						<h2 class="dot">클라우드를 제공하는 일은 자원 생성보다 넓습니다</h2>
						<p class="section-copy">연구실에서는 사용자 초대, 프로젝트 쿼터, 이미지와 네트워크, 데이터 공유, GPU 사용량, 실습 클러스터, 감사 로그가 한꺼번에 얽힙니다. Afterglow는 이 흐름을 연구 조직이 이해할 수 있는 콘솔로 묶습니다.</p>
					</div>
				</div>
				<div class="about-layout" data-reveal>
					<Card surface="subtle" padding="none" class="index-card">
						{#each overviewRows as row}
							<div class="index-row">
								<b>{row.num}</b>
								<div><strong>{row.title}</strong><p>{row.body}</p></div>
							</div>
						{/each}
					</Card>
					<div class="about-collage">
						<LandingFigure class="plate" src="/landing/plate-professor.svg" alt="교수와 연구원 협업 콜라주" />
						<LandingFigure class="plate" src="/landing/plate-console.svg" alt="클라우드 콘솔 콜라주" />
					</div>
				</div>
			</div>
		</section>

		<section id="capabilities" class="section">
			<div class="container">
				<div class="section-kicker" data-reveal>
					<span class="roman">III</span>
					<div>
						<h2 class="dot">연구 클라우드 제공에 필요한 표면을 한데 모읍니다</h2>
						<p class="section-copy">사용자는 실험을 시작하고, 운영자는 경계를 유지하고, 교수자는 팀 단위 자원 흐름을 확인할 수 있어야 합니다.</p>
					</div>
				</div>
				<div class="card-grid" data-reveal>
					{#each capabilities as card}
						<article class="cap-card">
							<Card surface="subtle" padding="none" class="cap-card-surface">
								<img src={card.src} alt={card.alt} loading="lazy" decoding="async" />
								<div class="cap-body">
									<div class="cap-meta"><span>{card.num}</span><span>{card.tag}</span></div>
									<h3>{card.title}</h3>
									<p>{card.body}</p>
								</div>
							</Card>
						</article>
					{/each}
				</div>
			</div>
		</section>

		<section id="workflow" class="section">
			<div class="container">
				<div class="section-kicker" data-reveal>
					<span class="roman">IV</span>
					<div>
						<h2 class="dot">연구실마다 다른 사용 흐름을 필터처럼 꺼내 봅니다</h2>
						<p class="section-copy">아래 항목을 누르면 관련 워크플로우가 강조됩니다. 실제 서비스 화면에서도 이런 식으로 자원, 상태, 작업 흐름이 연결됩니다.</p>
					</div>
				</div>
				<div class="labs-layout" data-reveal>
					<aside class="filter-panel">
						<Card surface="subtle" padding="none" class="filter-panel-surface">
							<h3 class="dot">워크플로우 인덱스</h3>
							<ToggleGroup value={selectedFilter} options={filters} onchange={selectFilter} size="sm" class="landing-workflow-filter" ariaLabel="워크플로우 필터" />
							<div class="progress-track" aria-hidden="true"><span class="progress-fill" id="workflow-progress" style={`width: ${progressWidth}`}></span></div>
						</Card>
					</aside>
					<div class="lab-list">
						{#each workflowCards as card}
							{@const matches = selectedFilter === 'all' || card.kind === selectedFilter}
							<article class="lab-card" class:is-muted={!matches} data-kind={card.kind}>
								<Card surface="subtle" padding="none" class="lab-card-surface">
									<img src={card.src} alt={card.alt} loading="lazy" decoding="async" />
									<div><h3>{card.title}</h3><p>{card.body}</p></div>
								</Card>
							</article>
						{/each}
						{#if visibleCount === 0}
							<p class="empty-state" id="workflow-empty" role="status" aria-live="polite">선택한 조건에 맞는 워크플로우가 없습니다. 전체를 선택해 다시 확인하세요.</p>
						{/if}
					</div>
				</div>
			</div>
		</section>

		<section class="section">
			<div class="container">
				<div class="section-kicker" data-reveal>
					<span class="roman">V</span>
					<div><h2 class="dot">제공 방식은 네 단계로 정리됩니다</h2></div>
				</div>
				<div data-reveal>
					<Card surface="subtle" padding="none" class="method-grid">
						{#each methodSteps as step}
							<article class="method-step">
								<div><b>{step.step}</b><h3>{step.title}</h3></div>
								{#if step.icon === 'observability'}
									<svg class="method-icon" viewBox="0 0 320 240" role="img" aria-label={step.alt}>
										<circle cx="48" cy="120" r="28" fill="none" stroke="currentColor" stroke-width="3" />
										<path d="m41 104 22 16-22 16z" fill="currentColor" />
										<path d="M76 120h28M222 120h18" fill="none" stroke="currentColor" stroke-dasharray="5 7" stroke-width="2.5" />
										<rect x="104" y="52" width="118" height="132" rx="10" fill="none" stroke="currentColor" stroke-width="3" />
										<path d="M124 160V78h78" fill="none" stroke="currentColor" stroke-width="2.5" opacity=".62" />
										<path d="M128 144c14-8 16-35 30-28s16 37 30 22 16-56 30-42" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="4" />
										<path d="M128 154c14-2 20-18 32-12s18 24 32 13 14-30 26-25" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="3" opacity=".55" />
										<circle cx="158" cy="116" r="4" fill="currentColor" /><circle cx="188" cy="138" r="4" fill="currentColor" /><circle cx="218" cy="96" r="4" fill="currentColor" />
										<rect x="240" y="58" width="56" height="124" rx="10" fill="none" stroke="currentColor" stroke-width="3" />
										<path d="M258 84h22M258 108h22M258 132h16M258 156h22" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="3" />
										<circle cx="252" cy="84" r="3" fill="currentColor" /><circle cx="252" cy="132" r="3" fill="currentColor" opacity=".58" /><circle cx="252" cy="156" r="3" fill="currentColor" opacity=".58" />
									</svg>
								{:else if step.icon === 'reuse'}
									<svg class="method-icon" viewBox="0 0 320 240" role="img" aria-label={step.alt}>
										<rect x="36" y="142" width="128" height="34" rx="8" fill="currentColor" opacity=".28" />
										<rect x="52" y="108" width="128" height="34" rx="8" fill="currentColor" opacity=".5" />
										<rect x="68" y="74" width="128" height="34" rx="8" fill="currentColor" opacity=".82" />
										<path d="M84 91h96M68 125h96M52 159h96" fill="none" stroke="currentColor" stroke-width="3" opacity=".42" />
										<circle cx="220" cy="92" r="38" fill="none" stroke="currentColor" stroke-width="4" />
										<path d="M220 70v24l17 10M246 64l-4 18-17-7" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="4" />
										<path d="M180 128h30M210 128l-10-10M210 128l-10 10" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="4" />
										<rect x="222" y="150" width="56" height="36" rx="8" fill="none" stroke="currentColor" stroke-width="3" opacity=".68" />
										<circle cx="238" cy="168" r="4" fill="currentColor" /><circle cx="254" cy="168" r="4" fill="currentColor" opacity=".55" /><circle cx="270" cy="168" r="4" fill="currentColor" opacity=".32" />
									</svg>
								{:else if step.src}
									<img src={step.src} alt={step.alt} loading="lazy" decoding="async" />
								{/if}
							</article>
						{/each}
					</Card>
				</div>
			</div>
		</section>

		<section id="work" class="section">
			<div class="container">
				<div class="section-kicker" data-reveal>
					<span class="roman">VI</span>
					<div>
						<h2 class="dot">실제 콘솔은 운영자가 빠르게 읽을 수 있어야 합니다</h2>
						<p class="section-copy">랜딩은 편집적으로 보이되, 제품 자체는 고밀도 운영 콘솔입니다. 대시보드, 관리자, 클러스터, 네트워크 화면을 안전한 제품 아트워크로 노출합니다.</p>
					</div>
				</div>
				<div data-reveal>
					<Card surface="subtle" padding="none" class="work-slab">
						<div class="work-grid">
							<LandingFigure class="screen-main" src="/landing/plate-kubernetes.svg" alt="Afterglow Kubernetes 클러스터 화면">Kubernetes 클러스터 / 노드와 워크로드</LandingFigure>
							<div class="screen-stack">
								<LandingFigure src="/landing/plate-security.svg" alt="Afterglow 관리자 개요 화면">관리자 개요 / 사용량과 서비스 상태</LandingFigure>
								<LandingFigure src="/landing/plate-network-topology.svg" alt="Afterglow 네트워크 토폴로지 화면">네트워크 토폴로지 / 연결 관계</LandingFigure>
							</div>
						</div>
					</Card>
				</div>
			</div>
		</section>

		<section class="section">
			<div class="container quote-panel">
				<div data-reveal>
					<span class="roman">VII</span>
					<blockquote class="dot">“실험 환경을 만드는 시간이 줄어들면, 연구자는 다시 질문에 집중할 수 있습니다”</blockquote>
					<ul class="glyphs" aria-label="대상 사용자와 조직">
						<li class="glyph">연구실</li><li class="glyph">교수자</li><li class="glyph">연구원</li><li class="glyph">실습팀</li><li class="glyph">연구 조직</li>
					</ul>
				</div>
				<div class="quote-visual" data-reveal>
					<LandingFigure class="plate" src="/landing/plate-kubernetes.svg" alt="Afterglow K8s 클러스터 목록 화면" />
					<LandingFigure class="plate" src="/landing/plate-network-topology.svg" alt="프로젝트와 워크로드를 잇는 라우터 토폴로지 콜라주" />
				</div>
			</div>
		</section>

		<section id="contact" class="section">
			<div class="container">
				<div class="cta" data-reveal>
					<div>
						<span class="eyebrow">VIII / Console ready</span>
						<h2 class="dot">연구실 클라우드 제공 방식을 정리할 준비가 되셨나요?</h2>
						<p class="section-copy">데모, PoC, 학내 연구실 배포 논의를 위해 연락 주세요.</p>
					</div>
					<Button variant="outline" size="lg" class="email-pill" href={`mailto:${email}`} ariaLabel="이메일 문의 보내기">문의</Button>
				</div>
			</div>
		</section>
	<footer class="footer">
		<div class="container">
			<div class="footer-grid">
				<div><h3>제품</h3><a href="#overview">개요</a><a href="#capabilities">제공 기능</a><a href="#workflow">워크플로우</a></div>
				<div><h3>연락</h3><a href={`mailto:${email}`}>{email}</a><a href="https://github.com/openstack-afterglow/openstack-afterglow">GitHub 저장소</a></div>
			</div>
			<p class="footer-copyright">© 2026 {siteName}. 연구 클라우드 운영 콘솔.</p>
			<div class="mega">{siteName}</div>
		</div>
	</footer>
	</div>
</div>

<style>
.landing-page {
		--landing-ease: cubic-bezier(.2, .8, .2, 1);
		--landing-container: 1180px;
		--landing-gutter: clamp(18px, 4vw, 44px);
		--landing-radius: 14px;
		position: relative;
		min-height: 100%;
		background: var(--gradient-editorial-canvas);
		color: var(--color-ink-0);
		font-family: var(--font-sans);
		font-size: 15px;
		line-height: 1.6;
		-webkit-font-smoothing: antialiased;
		text-rendering: optimizeLegibility;
		padding-top: 68px;
	}

	.landing-page::before {
		content: '';
		position: fixed;
		inset: 0;
		pointer-events: none;
		z-index: 0;
		opacity: 0.26;
		background-image: var(--pattern-editorial-grid);
		background-size: 72px 72px;
		mask-image: var(--gradient-editorial-grid-mask);
	}

	.landing-page > * { position: relative; z-index: 1; }
	.landing-page :global(img) { max-width: 100%; display: block; }
	.landing-page :global(a) { color: inherit; }
	.landing-page :global(button), .landing-page :global(input) { font: inherit; }
	.landing-page .container { width: min(var(--landing-container), calc(100% - var(--landing-gutter) * 2)); margin-inline: auto; }
	.landing-page .em { font-family: var(--font-sans); font-style: italic; font-weight: 500; color: var(--color-warm); }
	.landing-page .dot::after { content: '.'; color: var(--color-warm); }
	.landing-page h1, .landing-page h2, .landing-page h3, .landing-page p { margin: 0; }
	.landing-page :global(a:focus-visible), .landing-page :global(button:focus-visible) { outline: 2px solid var(--color-warm); outline-offset: 4px; box-shadow: var(--focus-ring); }

	.landing-page .skip-link {
		position: fixed; top: 12px; left: 16px; z-index: 80; min-height: 44px; display: inline-flex; align-items: center;
		padding: 0 14px; border: 1px solid var(--color-warm); border-radius: 999px; background: var(--color-ink-0); color: var(--color-surface-canvas);
		font-weight: 700; text-decoration: none; transform: translateY(-150%); transition: transform 160ms var(--landing-ease);
	}
	.landing-page .skip-link:focus-visible { transform: translateY(0); }

	.landing-page .top-strip {
		position: fixed; inset: 0 0 auto; z-index: 30; border-bottom: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%);
		background: color-mix(in oklab, var(--color-surface-canvas), transparent 8%); backdrop-filter: blur(18px);
	}
	.landing-page .nav { display: flex; min-height: 68px; min-width: 0; align-items: center; justify-content: space-between; gap: 22px; border-top: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); }
	.landing-page .brand { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 12px; text-decoration: none; font-weight: 700; letter-spacing: 0; }
	.landing-page .brand img { width: 34px; height: 34px; padding: 3px; border-radius: 9px; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); background: var(--color-surface-raised); object-fit: contain; }
	.landing-page .nav-links { display: flex; flex: 1 1 auto; min-width: 0; align-items: center; justify-content: center; gap: 4px; overflow-x: auto; color: var(--color-ink-1); font-size: 13px; scrollbar-width: none; white-space: nowrap; }
	.landing-page .nav-links::-webkit-scrollbar { display: none; }
	.landing-page .nav-links a { display: inline-flex; flex: 0 0 auto; align-items: center; min-height: 40px; padding: 7px 10px; border-radius: 999px; text-decoration: none; transition: background 160ms var(--landing-ease), color 160ms var(--landing-ease), box-shadow 160ms var(--landing-ease); }
	.landing-page .nav-links a:hover { background: color-mix(in oklab, var(--color-surface-raised), transparent 18%); color: var(--color-ink-0); }
	.landing-page .nav-links a.is-active { background: color-mix(in oklab, var(--color-warm), transparent 84%); color: var(--color-ink-0); box-shadow: inset 0 -2px 0 var(--color-warm); }
	.landing-page :global(.nav-cta), .landing-page :global(.landing-btn) { min-height: 44px; padding-inline: 16px; border-radius: 999px; font-size: 13px; font-weight: 700; }
	.landing-page :global(.nav-cta) { flex: 0 0 auto; border-color: color-mix(in oklab, var(--color-warm), var(--color-line) 40%); }
	.landing-page :global(.landing-btn) { min-height: 48px; padding-inline: 20px; }

	.landing-page .hero { min-height: calc(100svh - 68px); padding: clamp(56px, 8vw, 96px) 0 56px; display: grid; align-items: center; }
	.landing-page .hero-grid { display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(340px, .92fr); gap: clamp(28px, 5vw, 68px); align-items: center; }
	.landing-page .eyebrow { display: inline-flex; align-items: center; gap: 10px; color: var(--color-warm); font-family: var(--font-mono); font-size: 12px; letter-spacing: .12em; text-transform: uppercase; }
	.landing-page .eyebrow::before { content: ''; width: 36px; height: 1px; border-top: 1px dotted currentColor; }
	.landing-page h1 { max-width: 940px; margin-top: 22px; font-family: var(--font-sans); font-size: 112px; line-height: .92; font-weight: 700; letter-spacing: 0; text-wrap: balance; word-break: keep-all; overflow-wrap: normal; }
	.landing-page .lead { max-width: 670px; margin-top: 26px; color: var(--color-ink-1); font-size: 22px; line-height: 1.55; word-break: keep-all; }
	.landing-page .hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
	.landing-page .stat-rings { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 40px; max-width: 650px; }
	.landing-page .ring { min-height: 150px; padding: 16px; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); background: color-mix(in oklab, var(--color-surface-raised), transparent 16%); display: grid; align-content: space-between; position: relative; overflow: hidden; }
	.landing-page .ring::before { content: ''; position: absolute; right: -32px; top: -42px; width: 126px; height: 126px; border: 18px solid color-mix(in oklab, var(--color-warm), transparent 20%); border-left-color: transparent; border-radius: 50%; transform: rotate(var(--rot, 18deg)); }
	.landing-page .ring:nth-child(2)::before { border-color: color-mix(in oklab, var(--color-accent), transparent 18%); border-top-color: transparent; --rot: 62deg; }
	.landing-page .ring:nth-child(3)::before { border-color: color-mix(in oklab, var(--color-accent-2), transparent 20%); border-bottom-color: transparent; --rot: -18deg; }
	.landing-page .ring strong { font-family: var(--font-sans); font-size: 38px; line-height: 1; }
	.landing-page .ring span { color: var(--color-ink-2); font-size: 12px; word-break: keep-all; }
	.landing-page .collage { display: grid; grid-template-columns: .86fr 1fr; gap: 14px; align-items: end; }
	.landing-page :global(.plate) { position: relative; overflow: hidden; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); background: var(--color-surface-editorial-media); box-shadow: 0 24px 70px color-mix(in oklab, var(--color-surface-canvas), transparent 58%); }
	.landing-page :global(.plate img) { width: 100%; height: 100%; object-fit: cover; }
	.landing-page :global(.plate img[src$='.svg']) { object-fit: contain; background: var(--color-surface-editorial-media); }
	.landing-page :global(.plate.hero-main) { aspect-ratio: 4 / 5; border-radius: 28px 28px 4px 28px; transform: rotate(-2.5deg); }
	.landing-page :global(.plate.hero-side) { aspect-ratio: 1 / 1; border-radius: 4px 26px 26px 26px; transform: rotate(3deg); margin-bottom: 34px; }
	.landing-page :global(.plate.hero-wide) { grid-column: 1 / -1; aspect-ratio: 16 / 7; border-radius: 26px 4px 26px 26px; transform: rotate(.8deg); }

	.landing-page .section { padding: clamp(66px, 10vw, 126px) 0; border-top: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); }
	.landing-page #landing-content, .landing-page .section[id] { scroll-margin-top: 126px; }
	.landing-page .section-kicker { display: grid; grid-template-columns: 90px 1fr; gap: 20px; align-items: start; margin-bottom: 34px; }
	.landing-page .roman { color: var(--color-warm); font-family: var(--font-sans); font-style: italic; font-size: 28px; line-height: 1; }
	.landing-page .section h2 { max-width: 900px; font-family: var(--font-sans); font-size: 68px; line-height: .98; letter-spacing: 0; text-wrap: balance; word-break: keep-all; overflow-wrap: normal; }
	.landing-page .section-copy { max-width: 700px; margin-top: 18px; color: var(--color-ink-1); font-size: 20px; line-height: 1.65; word-break: keep-all; }
	.landing-page .about-layout { display: grid; grid-template-columns: minmax(0, .95fr) minmax(340px, 1.05fr); gap: 28px; align-items: stretch; }
	.landing-page :global(.index-card) { border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); background: color-mix(in oklab, var(--color-surface-raised), transparent 12%); overflow: hidden; }
	.landing-page .index-row { display: grid; grid-template-columns: 64px 1fr; gap: 16px; padding: 18px; border-bottom: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); }
	.landing-page .index-row:last-child { border-bottom: 0; }
	.landing-page .index-row b { color: var(--color-warm); font-family: var(--font-mono); font-size: 12px; }
	.landing-page .index-row strong { display: block; margin-bottom: 4px; font-size: 18px; }
	.landing-page .index-row p { color: var(--color-ink-2); font-size: 14px; word-break: keep-all; }
	.landing-page .about-collage { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
	.landing-page .about-collage :global(.plate:first-child) { aspect-ratio: 1 / 1.08; border-radius: 26px 4px 26px 26px; }
	.landing-page .about-collage :global(.plate:nth-child(2)) { aspect-ratio: 1 / 1.08; border-radius: 4px 26px 26px 26px; transform: translateY(34px); }

	.landing-page .card-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
	.landing-page .cap-card { min-height: 460px; display: block; }
	.landing-page :global(.cap-card-surface) { display: grid; grid-template-rows: 190px auto; height: 100%; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); overflow: hidden; background: color-mix(in oklab, var(--color-surface-raised), transparent 10%); }
	.landing-page :global(.cap-card-surface img) { height: 190px; width: 100%; object-fit: cover; border-bottom: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); }
	.landing-page .cap-body { padding: 18px; }
	.landing-page .cap-meta { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 18px; color: var(--color-ink-2); font-family: var(--font-mono); font-size: 12px; }
	.landing-page .cap-card h3 { font-family: var(--font-sans); font-size: 28px; line-height: 1.05; text-wrap: balance; word-break: keep-all; overflow-wrap: normal; }
	.landing-page .cap-card p { margin-top: 14px; color: var(--color-ink-1); font-size: 14px; word-break: keep-all; }

	.landing-page .labs-layout { display: grid; grid-template-columns: minmax(320px, .42fr) minmax(0, .58fr); gap: 20px; align-items: start; }
	.landing-page .filter-panel { position: sticky; top: 126px; }
	.landing-page :global(.filter-panel-surface) { border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); padding: 18px; background: color-mix(in oklab, var(--color-surface-raised), transparent 12%); }
	.landing-page .filter-panel h3 { font-family: var(--font-sans); font-size: 32px; line-height: 1.05; }
	.landing-page :global(.landing-workflow-filter) { display: flex; margin-top: 20px; border: 0; padding: 0; background: transparent; border-radius: 999px; }
	.landing-page :global(.landing-workflow-filter .toggle-option) { min-height: 36px; padding: 0 12px; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: 999px; background: transparent; color: var(--color-ink-1); cursor: pointer; transition: border-color 160ms var(--landing-ease), color 160ms var(--landing-ease), background 160ms var(--landing-ease), transform 160ms var(--landing-ease); }
	.landing-page :global(.landing-workflow-filter .toggle-option:hover) { border-color: var(--color-warm); color: var(--color-ink-0); }
	.landing-page :global(.landing-workflow-filter .toggle-option:active) { transform: translateY(1px); }
	.landing-page :global(.landing-workflow-filter .toggle-option[aria-pressed='true']) { border-color: var(--color-warm); background: color-mix(in oklab, var(--color-warm), transparent 84%); color: var(--color-ink-0); }
	.landing-page .progress-track { margin-top: 22px; height: 4px; border-radius: 999px; background: var(--color-line); overflow: hidden; }
	.landing-page .progress-fill { display: block; height: 100%; border-radius: inherit; background: var(--color-warm); transition: width 220ms var(--landing-ease); }
	.landing-page .lab-list { display: grid; gap: 12px; }
	.landing-page .lab-card { display: block; transition: opacity 180ms var(--landing-ease), transform 180ms var(--landing-ease), border-color 180ms var(--landing-ease); }
	.landing-page .lab-card.is-muted { opacity: .38; transform: scale(.985); }
	.landing-page :global(.lab-card-surface) { display: grid; grid-template-columns: 176px 1fr; gap: 18px; align-items: center; padding: 12px; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); background: color-mix(in oklab, var(--color-surface-raised), transparent 14%); }
	.landing-page :global(.lab-card-surface img) { aspect-ratio: 4 / 3; height: 132px; width: 176px; border-radius: 10px; object-fit: cover; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); }
	.landing-page .lab-card h3 { font-size: 20px; }
	.landing-page .lab-card p { color: var(--color-ink-1); word-break: keep-all; }
	.landing-page .empty-state { margin: 0; padding: 18px; border: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); color: var(--color-ink-2); background: color-mix(in oklab, var(--color-surface-raised), transparent 18%); word-break: keep-all; }

	.landing-page :global(.method-grid) { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: var(--landing-radius); overflow: hidden; }
	.landing-page .method-step { min-height: 300px; padding: 22px; border-right: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); background: color-mix(in oklab, var(--color-surface-raised), transparent 14%); display: grid; align-content: space-between; gap: 28px; }
	.landing-page .method-step:last-child { border-right: 0; }
	.landing-page .method-icon { aspect-ratio: 4 / 3; width: 100%; display: block; padding: 16px; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: 10px; background: color-mix(in oklab, var(--color-surface-canvas), transparent 10%); color: var(--color-accent); }
	.landing-page .method-step b { color: var(--color-warm); font-family: var(--font-mono); font-size: 12px; letter-spacing: .08em; }
	.landing-page .method-step h3 { margin-top: 10px; font-family: var(--font-sans); font-size: 25px; line-height: 1.05; }

	.landing-page :global(.work-slab) { padding: clamp(20px, 4vw, 36px); border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: 28px; background: color-mix(in oklab, var(--color-surface-canvas), var(--color-surface-raised) 74%); overflow: hidden; }
	.landing-page .work-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr); gap: 18px; align-items: center; }
	.landing-page :global(.screen-main), .landing-page :global(.screen-stack figure) { margin: 0; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); background: var(--color-surface-canvas); overflow: hidden; position: relative; box-shadow: 0 28px 70px color-mix(in oklab, var(--color-surface-canvas), transparent 48%); }
	.landing-page :global(.screen-main) { border-radius: 18px; transform: rotate(-1.1deg); }
	.landing-page :global(.screen-main img) { aspect-ratio: 16 / 9; width: 100%; height: 100%; object-fit: cover; object-position: left top; }
	.landing-page .screen-stack { display: grid; gap: 16px; }
	.landing-page :global(.screen-stack figure) { border-radius: 18px; transform: rotate(2deg); }
	.landing-page :global(.screen-stack figure:nth-child(2)) { transform: rotate(-2.2deg); }
	.landing-page :global(.screen-stack img) { aspect-ratio: 16 / 10; width: 100%; object-fit: cover; object-position: left top; }
	.landing-page :global(figcaption) { padding: 10px 12px; color: var(--color-ink-2); font-family: var(--font-mono); font-size: 12px; border-top: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); }

	.landing-page .quote-panel { display: grid; grid-template-columns: minmax(0, .9fr) minmax(320px, 1.1fr); gap: 24px; align-items: center; }
	.landing-page blockquote { margin: 0; font-family: var(--font-sans); font-size: 64px; line-height: 1.02; text-wrap: balance; word-break: keep-all; overflow-wrap: normal; }
	.landing-page .glyphs { display: flex; flex-wrap: wrap; gap: 10px; margin: 26px 0 0; padding: 0; list-style: none; }
	.landing-page .glyph { display: inline-flex; min-height: 48px; align-items: center; justify-content: center; padding: 0 18px; border: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); border-radius: 999px; color: var(--color-warm); font-family: var(--font-sans); font-size: 16px; font-weight: 600; letter-spacing: -.01em; white-space: nowrap; }
	.landing-page .quote-visual { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
	.landing-page .quote-visual :global(.plate) { aspect-ratio: 4 / 3; border-radius: 26px; }
	.landing-page .quote-visual :global(.plate:nth-child(2)) { transform: translateY(36px) rotate(2deg); }

	.landing-page .cta { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 22px; align-items: end; padding: clamp(26px, 5vw, 52px); border: 1px solid color-mix(in oklab, var(--color-warm), var(--color-line) 42%); border-radius: 30px; background: var(--gradient-editorial-cta), color-mix(in oklab, var(--color-surface-raised), transparent 8%); position: relative; overflow: hidden; }
	.landing-page .cta::before { content: 'AFTERGLOW'; position: absolute; right: -20px; bottom: -34px; color: color-mix(in oklab, var(--color-ink-0), transparent 92%); font-family: var(--font-sans); font-size: 180px; font-style: italic; line-height: .8; pointer-events: none; }
	.landing-page .cta h2 { position: relative; max-width: 780px; font-size: 78px; }
	.landing-page :global(.email-pill) { position: relative; display: inline-flex; align-items: center; gap: 10px; min-height: 48px; padding: 0 16px; border: 1px solid color-mix(in oklab, var(--color-line), transparent 34%); border-radius: 999px; background: var(--color-surface-canvas); color: var(--color-ink-0); font-family: var(--font-mono); }
	.landing-page :global(.email-pill:hover) { border-color: var(--color-warm); background: color-mix(in oklab, var(--color-surface-raised), transparent 10%); }
	.landing-page :global(.email-pill:active) { transform: translateY(1px); }

	.landing-page .footer { padding: 46px 0 34px; border-top: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%); color: var(--color-ink-2); }
	.landing-page .footer-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-bottom: 44px; }
	.landing-page .footer h3 { color: var(--color-ink-0); font-size: 13px; margin-bottom: 10px; }
	.landing-page .footer a { display: block; color: inherit; text-decoration: none; font-size: 13px; line-height: 1.9; }
	.landing-page .footer-copyright { color: var(--color-ink-2); font-family: var(--font-mono); font-size: 12px; }
	.landing-page .mega { font-family: var(--font-sans); font-style: italic; font-size: 160px; line-height: .78; color: color-mix(in oklab, var(--color-ink-0), transparent 76%); }

	.landing-page [data-reveal] { opacity: 1; transform: none; }
	:global(.landing-page.reveal-enabled) [data-reveal]:not(.is-visible) { opacity: 0; transform: translateY(24px); }
	:global(.landing-page.reveal-enabled.reveal-ready) [data-reveal] { transition: opacity 600ms var(--landing-ease), transform 600ms var(--landing-ease); }

	@media (prefers-reduced-motion: reduce) {
		.landing-page :global(*), .landing-page :global(*::before), .landing-page :global(*::after) { scroll-behavior: auto !important; transition-duration: 1ms !important; animation-duration: 1ms !important; }
		.landing-page [data-reveal], :global(.landing-page.reveal-enabled) [data-reveal]:not(.is-visible) { opacity: 1; transform: none; transition: none; }
		.landing-page .top-strip { transition: none; }
	}

	@media (max-width: 1080px) {
		.landing-page .hero-grid, .landing-page .about-layout, .landing-page .labs-layout, .landing-page .work-grid, .landing-page .quote-panel { grid-template-columns: 1fr; }
		.landing-page .card-grid, .landing-page :global(.method-grid) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
		.landing-page .filter-panel { position: static; }
		.landing-page h1 { font-size: 84px; }
		.landing-page .section h2 { font-size: 56px; }
		.landing-page blockquote { font-size: 54px; }
		.landing-page .cta h2 { font-size: 60px; }
		.landing-page .cta::before { font-size: 142px; }
		.landing-page .mega { font-size: 124px; }
	}

	@media (max-width: 880px) {
		.landing-page .nav { min-height: 60px; }
		.landing-page .hero { min-height: auto; }
		.landing-page .stat-rings, .landing-page .card-grid, .landing-page :global(.method-grid) { grid-template-columns: 1fr; }
		.landing-page .collage { grid-template-columns: 1fr 1fr; }
		.landing-page :global(.plate.hero-wide) { grid-column: auto; }
		.landing-page .section-kicker { grid-template-columns: 1fr; }
		.landing-page :global(.lab-card-surface) { grid-template-columns: 128px 1fr; }
		.landing-page :global(.lab-card-surface img) { width: 128px; height: 106px; }
		.landing-page .cta { grid-template-columns: 1fr; }
		.landing-page h1 { font-size: 64px; }
		.landing-page .lead { font-size: 19px; }
		.landing-page .section h2 { font-size: 44px; }
		.landing-page .section-copy { font-size: 18px; }
		.landing-page blockquote { font-size: 42px; }
		.landing-page .cta h2 { font-size: 44px; }
		.landing-page .cta::before { font-size: 96px; }
		.landing-page .mega { font-size: 86px; }
	}

	@media (max-width: 560px) {
		.landing-page { --landing-gutter: 16px; font-size: 14px; }
		.landing-page :global(.nav-cta) { display: none; }
		.landing-page .nav-links { justify-content: flex-start; }
		.landing-page h1 { font-size: 46px; }
		.landing-page .lead { font-size: 17px; }
		.landing-page .section h2 { font-size: 36px; }
		.landing-page .section-copy { font-size: 16px; }
		.landing-page blockquote { font-size: 34px; }
		.landing-page .cta h2 { font-size: 35px; }
		.landing-page .cta::before { font-size: 70px; }
		.landing-page .mega { font-size: 62px; }
		.landing-page .collage, .landing-page .about-collage, .landing-page .quote-visual { grid-template-columns: 1fr; }
		.landing-page .about-collage :global(.plate:nth-child(2)), .landing-page .quote-visual :global(.plate:nth-child(2)) { transform: none; }
		.landing-page :global(.lab-card-surface) { grid-template-columns: 1fr; }
		.landing-page :global(.lab-card-surface img) { width: 100%; height: auto; }
		.landing-page :global(.screen-main), .landing-page :global(.screen-stack figure) { transform: none; }
	}
</style>
