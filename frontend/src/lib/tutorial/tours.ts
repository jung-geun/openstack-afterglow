export type TourId = 'vm-create' | 'volume' | 'drover';

export const TOUR_QUERY_KEY = 'tour';
export const TOUR_STORAGE_KEY = 'afterglow_tour';

export interface TourStep {
	/** data-tour 앵커 셀렉터 (하이라이트 대상) */
	element: string;
	/** 이 step을 보여주기 전에 이동할 경로 */
	route?: string;
	title: string;
	description: string;
	/** 'click'이면 실제 클릭으로 다음 step 진행 (팝오버 '다음' 버튼 없음) */
	advanceOn?: 'click';
	/** 진행 트리거 셀렉터 — 생략 시 element 자체 클릭으로 진행 */
	advanceElement?: string;
	waitTimeoutMs?: number;
}

export interface TourDefinition {
	id: TourId;
	label: string;
	summary: string;
	steps: TourStep[];
}

export const tours: TourDefinition[] = [
	{
		id: 'vm-create',
		label: 'VM 생성',
		summary: '위저드로 인스턴스를 만들고 배포 과정을 지켜봅니다.',
		steps: [
			{
				element: '[data-tour="vm-create-open"]',
				route: '/dashboard',
				title: 'VM 생성 시작',
				description: 'VM 생성 버튼을 눌러 인스턴스 생성 위저드를 열어보세요.',
				advanceOn: 'click',
			},
			{
				element: '[data-tour="wizard-panel"]',
				title: '부팅 소스 선택',
				description:
					'OS 이미지를 하나 선택하고 아래 "다음 →" 버튼을 눌러보세요. 위저드는 부팅 소스 → 플레이버 → 라이브러리 → 전략 → 설정 → 리뷰 순서로 진행됩니다.',
				advanceOn: 'click',
				advanceElement: '[data-tour="wizard-next"]',
			},
			{
				element: '[data-tour="wizard-nav"]',
				title: '단계 진행과 배포',
				description:
					'남은 단계도 같은 방식으로 채우며 진행하세요. 마지막 리뷰 단계에서 "VM 생성"을 누르면 배포가 시작되고, 완료되면 대시보드에서 새 인스턴스를 확인할 수 있습니다.',
			},
		],
	},
	{
		id: 'volume',
		label: '볼륨 생성·관리',
		summary: '블록 볼륨을 만들고 목록에서 관리 작업을 살펴봅니다.',
		steps: [
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
		],
	},
	{
		id: 'drover',
		label: 'Drover 클러스터',
		summary: 'k3s Kubernetes 클러스터를 프로비저닝하고 접속 정보를 받습니다.',
		steps: [
			{
				element: '[data-tour="drover-create-open"]',
				route: '/dashboard/drover',
				title: '클러스터 생성 열기',
				description: '+ 클러스터 생성 버튼을 눌러 Drover 클러스터 생성 폼을 열어보세요.',
				advanceOn: 'click',
			},
			{
				element: '[data-tour="drover-create-form"]',
				title: '클러스터 구성',
				description:
					'클러스터 이름, 에이전트 노드 수, 플레이버, 네트워크를 설정한 뒤 "생성" 버튼을 누르세요. 템플릿을 선택하면 권장 구성이 자동으로 채워집니다.',
				advanceOn: 'click',
				advanceElement: '[data-tour="drover-create-submit"]',
			},
			{
				element: '[data-tour="drover-progress"]',
				title: '프로비저닝 진행',
				description:
					'VM 생성 → k3s 설치 → 완료 순으로 진행 상황이 실시간 표시됩니다. 완료 후 닫기를 누르면 목록 카드에서 kubeconfig를 내려받아 바로 kubectl로 접속할 수 있습니다.',
			},
		],
	},
];

export function isTourId(value: unknown): value is TourId {
	return value === 'vm-create' || value === 'volume' || value === 'drover';
}

export function getTour(id: unknown): TourDefinition | null {
	if (!isTourId(id)) return null;
	return tours.find((tour) => tour.id === id) ?? null;
}
