import { get } from 'svelte/store';
import { betaFeatures } from '$lib/stores/betaFeatures';
import { sidebarOpen } from '$lib/stores/sidebar';

export type TourId = 'vm-create' | 'volume' | 'drover';

export const TOUR_QUERY_KEY = 'tour';
export const TOUR_STORAGE_KEY = 'afterglow_tour';

export interface TourStep {
	/** data-tour 앵커 셀렉터 (하이라이트 대상) */
	element: string;
	/** 이 step을 보여주기 전에 이동할 경로 */
	route?: string;
	/** 하이라이트 직전 실행. 모바일 드로어 열기 등 사전 준비용. route 이동/auto-close 이후에 실행된다. */
	prepare?: () => void | Promise<void>;
	title: string;
	description: string;
	/**
	 * 'click'이면 실제 클릭으로 다음 step 진행 (팝오버 '다음' 버튼 없음).
	 * 'wizard'이면 위저드 단계(wizardStep) 변화를 따라 팝오버가 이동한다(자체 '다음' 버튼 없음).
	 */
	advanceOn?: 'click' | 'wizard';
	/** 이 팝오버가 대응하는 위저드 raw 단계 번호($wizard.step). 엔진이 afterglow:wizard-step 이벤트로 매핑한다. */
	wizardStep?: number;
	/** 진행 트리거 셀렉터 — 생략 시 element 자체 클릭으로 진행 */
	advanceElement?: string;
	/** 이 셀렉터 클릭 시 투어를 한 단계 뒤로 (예: 위저드 "← 이전" 버튼) */
	backElement?: string;
	/** 이 셀렉터 클릭 시 투어를 종료 (예: 위저드 "취소"/닫기 버튼) */
	cancelElement?: string;
	/** 하이라이트 전에 이 요소가 나타날 때까지 대기 (로딩 상태 회피용) */
	readyElement?: string;
	/** 표시 시점에 true면 이 step을 건너뛴다 (진행 방향 유지) */
	skipIf?: () => boolean;
	waitTimeoutMs?: number;
}

export interface TourDefinition {
	id: TourId;
	label: string;
	summary: string;
	steps: TourStep[];
}

const TOUR_META: Record<TourId, { label: string; summary: string }> = {
	'vm-create': { label: 'VM 생성', summary: '위저드로 인스턴스를 만들고 배포 과정을 지켜봅니다.' },
	volume: { label: '볼륨 생성·관리', summary: '블록 볼륨을 만들고 목록에서 관리 작업을 살펴봅니다.' },
	drover: { label: 'Drover 클러스터', summary: 'k3s Kubernetes 클러스터를 프로비저닝하고 접속 정보를 받습니다.' },
};

/**
 * VM 생성 투어 — 위저드 표시 단계에 맞춰 동적으로 구성한다.
 * 라이브러리 단계는 libraryConsume 베타가 켜져 있을 때만 포함되고,
 * (베타가 켜져 있어도) 위저드가 해당 단계를 노출하지 않으면(비 Ubuntu 이미지 등)
 * skipIf 로 런타임에 건너뛴다.
 */
function vmCreateSteps(): TourStep[] {
	const steps: TourStep[] = [
		{
			element: '[data-tour="vm-create-open"]',
			route: '/dashboard',
			prepare: async () => {
				// 모바일(md 미만)에서 사이드바는 닫힌 off-canvas 드로어라 VM 생성 버튼이 화면 밖에 있다.
				// 드로어를 열고 슬라이드 인 트랜지션(duration-200)이 끝난 뒤 하이라이트하도록 대기한다.
				if (typeof window !== 'undefined' && window.innerWidth < 768) {
					sidebarOpen.open();
					await new Promise((resolve) => setTimeout(resolve, 250));
				}
			},
			title: 'VM 생성 시작',
			description: 'VM 생성 버튼을 눌러 인스턴스 생성 위저드를 열어보세요.',
			advanceOn: 'click',
		},
		{
			element: '[data-tour="wizard-panel"]',
			title: '이미지 선택',
			description: 'VM을 부팅할 OS 이미지를 하나 선택하세요. 선택하면 자동으로 다음 단계로 이동합니다.',
			advanceOn: 'wizard',
			wizardStep: 1,
			cancelElement: '[data-tour="wizard-cancel"]',
			// 위저드 데이터 로딩이 끝나 본문이 나타난 뒤에 하이라이트한다
			readyElement: '[data-tour="wizard-body"]',
			waitTimeoutMs: 20000,
		},
		{
			element: '[data-tour="wizard-panel"]',
			title: '플레이버 선택',
			description:
				'플레이버는 VM의 vCPU · 메모리 · 디스크 스펙입니다. 프로젝트 남은 쿼터 안에서 생성 가능한 플레이버만 표시되고, GPU 플레이버는 스케줄러가 가용 호스트를 자동 선택합니다. 하나 선택하면 자동으로 다음 단계로 이동합니다.',
			advanceOn: 'wizard',
			wizardStep: 2,
			cancelElement: '[data-tour="wizard-cancel"]',
		},
	];
	if (get(betaFeatures).libraryConsume) {
		steps.push({
			element: '[data-tour="wizard-panel"]',
			title: '라이브러리 (베타)',
			description:
				'AI/ML 라이브러리 레이어를 VM에 얹을 수 있는 베타 기능입니다. 필요한 레이어를 고르거나, 선택 없이 "다음 →"으로 건너뛸 수 있습니다.',
			advanceOn: 'wizard',
			wizardStep: 3,
			cancelElement: '[data-tour="wizard-cancel"]',
			// Ubuntu 계열 이미지가 아니면 위저드가 이 단계를 숨긴다 — 스텝퍼에 없으면 투어도 건너뛴다
			skipIf: () =>
				!document.querySelector('[data-tour="wizard-stepper"]')?.textContent?.includes('라이브러리'),
		});
	}
	steps.push(
		{
			element: '[data-tour="wizard-panel"]',
			title: '기본 설정 확인',
			description:
				'VM 이름(비우면 자동 생성), 네트워크, SSH 키페어, 보안 그룹, 가용 영역, 루트 디스크 크기를 확인하세요. 기본값 그대로도 생성할 수 있습니다. 확인했으면 "다음 →"을 누르세요.',
			advanceOn: 'wizard',
			wizardStep: 5,
			cancelElement: '[data-tour="wizard-cancel"]',
		},
		{
			element: '[data-tour="wizard-panel"]',
			title: '배포',
			description:
				'선택한 구성 요약을 마지막으로 확인하세요. "VM 생성" 버튼을 누르면 부트 볼륨 생성 → 인스턴스 생성 순으로 배포가 시작됩니다.',
			wizardStep: 6,
			advanceOn: 'click',
			advanceElement: '[data-tour="wizard-next"]',
			cancelElement: '[data-tour="wizard-cancel"]',
		},
		{
			element: '[data-tour="dashboard-recent"]',
			title: '배포 완료',
			description:
				'배포가 끝나면 대시보드로 돌아옵니다. 최근 인스턴스 목록 맨 위에 방금 만든 VM이 추가된 것을 확인하세요. 이름을 클릭하면 상세 화면으로 이동합니다.',
			waitTimeoutMs: 20000,
		},
	);
	return steps;
}

function volumeSteps(): TourStep[] {
	return [
		{
			element: '[data-tour="volume-create-open"]',
			route: '/dashboard/volumes',
			title: '볼륨 생성 열기',
			description: '+ 볼륨 생성 버튼을 눌러 생성 폼을 열어보세요.',
			advanceOn: 'click',
		},
		{
			element: '[data-tour="volume-create-form"]',
			title: '볼륨 정보 입력',
			description: '볼륨 이름과 크기(GB)를 입력한 뒤 "생성" 버튼을 누르세요. 이름을 입력해야 버튼이 활성화됩니다.',
			advanceOn: 'click',
			advanceElement: '[data-tour="volume-create-submit"]',
		},
		{
			element: '[data-tour="volume-list"]',
			title: '볼륨 관리',
			description:
				'방금 만든 볼륨이 목록에 추가됐습니다. 행을 클릭하면 상세 패널이 열리고, 우측 액션 메뉴에서 확장·인스턴스 연결·삭제 등을 수행할 수 있습니다.',
		},
	];
}

function droverSteps(): TourStep[] {
	return [
		{
			element: '[data-tour="drover-create-open"]',
			route: '/dashboard/drover',
			title: '클러스터 생성 열기',
			description: '+ 클러스터 생성 버튼을 눌러 Drover 클러스터 생성 폼을 열어보세요.',
			advanceOn: 'click',
		},
		{
			element: '[data-tour="drover-name"]',
			title: '클러스터 이름',
			description: '클러스터 이름을 입력하세요. 비워두면 자동으로 생성됩니다.',
		},
		{
			element: '[data-tour="drover-os"]',
			title: 'OS 타입',
			description: '노드 OS를 선택하세요. Ubuntu(cloud-init) 또는 CoreOS(Ignition) 중 하나를 클릭하면 다음으로 진행됩니다.',
			advanceOn: 'click',
		},
		{
			element: '[data-tour="drover-masters"]',
			title: '마스터 수',
			description: '컨트롤 플레인 구성을 선택하세요. 1(단일) 또는 3(HA — embedded etcd, API LB 자동 생성) 중 하나를 클릭하면 다음으로 진행됩니다.',
			advanceOn: 'click',
		},
		{
			element: '[data-tour="drover-agents"]',
			title: '에이전트 수',
			description: '워커(에이전트) 노드 수를 0~10 사이에서 입력하세요.',
		},
		{
			element: '[data-tour="drover-flavor"]',
			title: '에이전트 플레이버',
			description: '에이전트 노드의 VM 스펙을 선택하세요. "기본값 사용"을 그대로 둬도 됩니다.',
		},
		{
			element: '[data-tour="drover-create-submit"]',
			title: '클러스터 생성',
			description: '"생성" 버튼을 누르면 VM 프로비저닝과 k3s 설치가 시작됩니다.',
			advanceOn: 'click',
		},
		{
			element: '[data-tour="drover-progress"]',
			title: '프로비저닝 진행',
			description:
				'VM 생성 → k3s 설치 → 완료 순으로 진행 상황이 실시간 표시됩니다. 완료 후 닫기를 누르면 목록 카드에서 kubeconfig를 내려받아 바로 kubectl로 접속할 수 있습니다.',
		},
	];
}

const STEP_BUILDERS: Record<TourId, () => TourStep[]> = {
	'vm-create': vmCreateSteps,
	volume: volumeSteps,
	drover: droverSteps,
};

/** 시작 버튼 등에서 시나리오 메타를 나열할 때 사용 (steps는 시작 시점에 빌드) */
export const tours: ReadonlyArray<{ id: TourId; label: string; summary: string }> = (
	Object.keys(TOUR_META) as TourId[]
).map((id) => ({ id, ...TOUR_META[id] }));

export function isTourId(value: unknown): value is TourId {
	return value === 'vm-create' || value === 'volume' || value === 'drover';
}

/** 호출 시점의 베타 설정 등을 반영해 투어 정의를 동적으로 빌드한다. */
export function getTour(id: unknown): TourDefinition | null {
	if (!isTourId(id)) return null;
	return { id, ...TOUR_META[id], steps: STEP_BUILDERS[id]() };
}
