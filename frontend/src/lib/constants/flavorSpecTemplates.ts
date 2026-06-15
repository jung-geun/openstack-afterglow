// Flavor extra spec 템플릿 카탈로그.
// FlavorExtraSpecsTab의 "템플릿에서 선택" UI가 사용한다.
// valueType:
//  - enum: options 중 선택
//  - number: 숫자 입력
//  - text: 자유 입력
//  - gpu_alias: GPU alias 드롭다운 + 개수 → "ALIAS:N" 값 생성 (pci_passthrough:alias 전용)

export interface FlavorSpecTemplate {
	key: string;
	category: string;
	label: string;
	description: string;
	valueType: 'enum' | 'number' | 'text' | 'gpu_alias';
	options?: string[];
	placeholder?: string;
	defaultValue?: string;
}

export const FLAVOR_SPEC_TEMPLATES: FlavorSpecTemplate[] = [
	// === GPU ===
	{
		key: 'pci_passthrough:alias',
		category: 'GPU',
		label: 'GPU Passthrough',
		description: 'PCI alias 기반 GPU 할당. 값 형식: alias:개수 (예: RTX3090:1)',
		valueType: 'gpu_alias',
	},
	{
		key: 'hw:hide_hypervisor_id',
		category: 'GPU',
		label: '하이퍼바이저 ID 숨김',
		description: 'NVIDIA 드라이버의 VM 감지 우회 (GPU passthrough 시 권장)',
		valueType: 'enum',
		options: ['true'],
		defaultValue: 'true',
	},
	// === CPU ===
	{
		key: 'hw:numa_nodes',
		category: 'CPU',
		label: 'NUMA 노드 수',
		description: '게스트에 노출할 NUMA 노드 수',
		valueType: 'number',
		placeholder: '예: 2',
	},
	{
		key: 'hw:cpu_policy',
		category: 'CPU',
		label: 'CPU 정책',
		description: 'dedicated: 물리 CPU 고정(pinning), shared: 공유',
		valueType: 'enum',
		options: ['shared', 'dedicated'],
	},
	{
		key: 'hw:cpu_thread_policy',
		category: 'CPU',
		label: 'CPU 스레드 정책',
		description: 'hw:cpu_policy=dedicated일 때 SMT 스레드 배치 정책',
		valueType: 'enum',
		options: ['prefer', 'isolate', 'require'],
	},
	{
		key: 'hw:cpu_sockets',
		category: 'CPU',
		label: 'CPU 소켓 수',
		description: '게스트 가상 CPU 토폴로지의 소켓 수',
		valueType: 'number',
		placeholder: '예: 1',
	},
	{
		key: 'hw:cpu_cores',
		category: 'CPU',
		label: 'CPU 코어 수',
		description: '게스트 가상 CPU 토폴로지의 소켓당 코어 수',
		valueType: 'number',
		placeholder: '예: 8',
	},
	{
		key: 'hw:cpu_threads',
		category: 'CPU',
		label: 'CPU 스레드 수',
		description: '게스트 가상 CPU 토폴로지의 코어당 스레드 수',
		valueType: 'number',
		placeholder: '예: 2',
	},
	// === 메모리 ===
	{
		key: 'hw:mem_page_size',
		category: '메모리',
		label: '메모리 페이지 크기',
		description: 'hugepage 사용 설정 (NUMA/SR-IOV 워크로드에 권장)',
		valueType: 'enum',
		options: ['small', 'large', '2MB', '1GB'],
	},
	// === QoS ===
	{
		key: 'quota:cpu_shares',
		category: 'QoS',
		label: 'CPU 가중치',
		description: '호스트 CPU 경합 시 상대적 가중치 (기본 1024)',
		valueType: 'number',
		placeholder: '예: 2048',
	},
	{
		key: 'quota:disk_read_bytes_sec',
		category: 'QoS',
		label: '디스크 읽기 제한 (B/s)',
		description: '초당 디스크 읽기 바이트 제한',
		valueType: 'number',
		placeholder: '예: 104857600 (100MB/s)',
	},
	{
		key: 'quota:disk_write_bytes_sec',
		category: 'QoS',
		label: '디스크 쓰기 제한 (B/s)',
		description: '초당 디스크 쓰기 바이트 제한',
		valueType: 'number',
		placeholder: '예: 104857600 (100MB/s)',
	},
];

export const FLAVOR_SPEC_CATEGORIES = [...new Set(FLAVOR_SPEC_TEMPLATES.map((t) => t.category))];
