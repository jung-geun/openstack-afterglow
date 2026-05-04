export interface NavItem {
  label: string;
  href: string;
  service: string | null;
}

export interface NavSection {
  label: string;
  prefix: string;
  extraPrefixes?: string[];
  icon: string;
  service?: string | null;
  items: NavItem[];
}

export const userNavSections: NavSection[] = [
  {
    label: 'Compute',
    prefix: '/dashboard/compute',
    extraPrefixes: [],
    icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2',
    items: [
      { label: '인스턴스', href: '/dashboard/compute/instances', service: null },
      { label: '이미지', href: '/dashboard/compute/images', service: null },
    ],
  },
  {
    label: '볼륨',
    prefix: '/dashboard/volumes',
    extraPrefixes: [],
    icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4',
    items: [
      { label: '볼륨 목록', href: '/dashboard/volumes', service: null },
      { label: '볼륨 백업', href: '/dashboard/volumes/backups', service: null },
      { label: '볼륨 스냅샷', href: '/dashboard/volumes/snapshots', service: null },
    ],
  },
  {
    label: 'File Storage',
    prefix: '/dashboard/file-storage',
    extraPrefixes: [],
    icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
    service: 'manila',
    items: [
      { label: '파일 스토리지', href: '/dashboard/file-storage', service: null },
      { label: '스냅샷', href: '/dashboard/file-storage/snapshots', service: null },
      { label: 'Share 네트워크', href: '/dashboard/file-storage/networks', service: null },
      { label: 'Security Service', href: '/dashboard/file-storage/security-services', service: null },
    ],
  },
  {
    label: '라이브러리',
    prefix: '/dashboard/library',
    extraPrefixes: ['/dashboard/file-storage/manage'],
    icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    items: [
      { label: '레이어 카탈로그', href: '/dashboard/library', service: null },
      { label: '템플릿', href: '/dashboard/library/templates', service: null },
      { label: '라이브러리 관리', href: '/dashboard/file-storage/manage', service: null },
    ],
  },
  {
    label: '컨테이너',
    prefix: '/dashboard/containers',
    extraPrefixes: ['/dashboard/drover'],
    icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
    service: 'containers',
    items: [
      { label: 'K8s 클러스터', href: '/dashboard/containers/clusters', service: 'magnum' },
      { label: '컨테이너', href: '/dashboard/containers/instances', service: 'zun' },
      { label: 'Drover', href: '/dashboard/drover', service: 'k3s' },
    ],
  },
  {
    label: 'Database',
    prefix: '/dashboard/database',
    extraPrefixes: [],
    icon: 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3M4 7v5c0 1.657 3.582 3 8 3s8-1.343 8-3V7M4 7c0 1.657 3.582 3 8 3s8-1.343 8-3M4 12v5c0 1.657 3.582 3 8 3s8-1.343 8-3v-5',
    service: 'trove',
    items: [
      { label: 'DB 인스턴스', href: '/dashboard/database/instances', service: null },
    ],
  },
  {
    label: 'Object Storage',
    prefix: '/dashboard/object-storage',
    extraPrefixes: [],
    icon: 'M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z',
    service: 'swift',
    items: [
      { label: '버킷', href: '/dashboard/object-storage/buckets', service: null },
    ],
  },
  {
    label: '네트워크',
    prefix: '/dashboard/network',
    extraPrefixes: [],
    icon: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
    items: [
      { label: '네트워크', href: '/dashboard/network/networks', service: null },
      { label: 'Floating IP', href: '/dashboard/network/floating-ips', service: null },
      { label: '라우터', href: '/dashboard/network/routers', service: null },
      { label: '로드밸런서', href: '/dashboard/network/loadbalancers', service: null },
      { label: '보안 그룹', href: '/dashboard/network/security-groups', service: null },
    ],
  },
];

export const adminNavSections: NavSection[] = [
  {
    label: 'Compute',
    prefix: '/admin/instances',
    icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2',
    items: [
      { label: '전체 인스턴스', href: '/admin/instances', service: null },
      { label: 'Flavor', href: '/admin/flavors', service: null },
      { label: '이미지', href: '/admin/images', service: null },
      { label: '하이퍼바이저', href: '/admin/hypervisors', service: null },
      { label: 'GPU', href: '/admin/gpu', service: null },
    ],
  },
  {
    label: '스토리지',
    prefix: '/admin/volumes',
    icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4',
    items: [
      { label: '전체 볼륨', href: '/admin/volumes', service: null },
      { label: '파일 스토리지', href: '/admin/file-storage', service: 'manila' },
      { label: 'DB 인스턴스', href: '/admin/database-instances', service: 'trove' },
      { label: 'Object Storage', href: '/admin/object-storage', service: 'swift' },
    ],
  },
  {
    label: '라이브러리',
    prefix: '/admin/libraries',
    icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    items: [
      { label: '라이브러리 관리', href: '/admin/libraries', service: null },
    ],
  },
  {
    label: '네트워크',
    prefix: '/admin/topology',
    icon: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
    items: [
      { label: '토폴로지', href: '/admin/topology', service: null },
      { label: '네트워크', href: '/admin/networks', service: null },
      { label: 'Floating IP', href: '/admin/floating-ips', service: null },
      { label: '라우터', href: '/admin/routers', service: null },
      { label: '포트', href: '/admin/ports', service: null },
    ],
  },
  {
    label: '컨테이너',
    prefix: '/admin/containers',
    icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
    items: [
      { label: '전체 컨테이너', href: '/admin/containers', service: 'zun' },
      { label: 'Drover', href: '/admin/drover', service: 'k3s' },
    ],
  },
  {
    label: '모니터링',
    prefix: '/admin/monitoring',
    icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    items: [
      { label: '통합 모니터링', href: '/admin/monitoring', service: null },
    ],
  },
  {
    label: '시스템',
    prefix: '/admin/services',
    icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z',
    items: [
      { label: '서비스 상태', href: '/admin/services', service: null },
      { label: 'Notion 연동', href: '/admin/notion', service: null },
    ],
  },
  {
    label: 'Identity',
    prefix: '/admin/users',
    icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z',
    items: [
      { label: '사용자', href: '/admin/users', service: null },
      { label: '프로젝트', href: '/admin/projects', service: null },
      { label: '쿼터', href: '/admin/quotas', service: null },
      { label: '그룹', href: '/admin/groups', service: null },
      { label: '역할', href: '/admin/roles', service: null },
    ],
  },
];

export function allNavItems(isAdmin: boolean): Array<NavItem & { section: string }> {
  const sections = isAdmin ? adminNavSections : userNavSections;
  return sections.flatMap((s) =>
    s.items.map((item) => ({ ...item, section: s.label }))
  );
}
