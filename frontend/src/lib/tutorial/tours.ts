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
				title: '이미지 선택',
				description: 'VM을 부팅할 OS 이미지를 하나 선택하고 아래 "다음 →" 버튼을 누르세요.',
				advanceOn: 'click',
				advanceElement: '[data-tour="wizard-next"]',
			},
			{
				element: '[data-tour="wizard-panel"]',
				title: '플레이버 선택',
				description:
					'플레이버는 VM의 vCPU · 메모리 · 디스크 스펙입니다. 프로젝트 남은 쿼터 안에서 생성 가능한 플레이버만 표시되고, GPU 플레이버는 스케줄러가 가용 호스트를 자동 선택합니다. 하나 선택하고 "다음 →"을 누르세요.',
				advanceOn: 'click',
				advanceElement: '[data-tour="wizard-next"]',
			},
			{
				element: '[data-tour="wizard-panel"]',
				title: '기본 설정 확인',
				description:
					'VM 이름(비우면 자동 생성), 네트워크, SSH 키페어, 보안 그룹, 가용 영역, 루트 디스크 크기를 확인하세요. 기본값 그대로도 생성할 수 있습니다. 확인했으면 "다음 →"을 누르세요.',
				advanceOn: 'click',
				advanceElement: '[data-tour="wizard-next"]',
			},
			{
				element: '[data-tour="wizard-panel"]',
				title: '배포',
				description:
					'선택한 구성 요약을 마지막으로 확인하세요. "VM 생성" 버튼을 누르면 부트 볼륨 생성 → 인스턴스 생성 순으로 배포가 시작됩니다.',
				advanceOn: 'click',
				advanceElement: '[data-tour="wizard-next"]',
			},
			{
				element: '[data-tour="dashboard-recent"]',
				title: '배포 완료',
				description:
					'배포가 끝나면 대시보드로 돌아옵니다. 최근 인스턴스 목록 맨 위에 방금 만든 VM이 추가된 것을 확인하세요. 이름을 클릭하면 상세 화면으로 이동합니다.',
				waitTimeoutMs: 20000,
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
