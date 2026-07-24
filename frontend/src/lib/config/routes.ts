// Afterglow route label map
// URL path segment → Korean/English display label
// Used to auto-derive breadcrumbs in TopBar from $page.url.pathname

export const ROUTE_LABELS: Record<string, string> = {
  // Top level
  dashboard: '대시보드',
  admin: 'ADMIN',

  // Overview
  'my-resources': '내 리소스',
  notifications: '알림함',

  // Compute
  compute: 'COMPUTE',
  instances: '인스턴스',
  keypairs: '키페어',
  images: '이미지',
  flavors: 'Flavor',
  hypervisors: '하이퍼바이저',
  gpu: 'GPU',

  // Volumes
  volumes: '볼륨',
  backups: '볼륨 백업',
  snapshots: '볼륨 스냅샷',

  // File Storage
  'file-storage': 'FILE STORAGE',
  manage: '사전 빌드 파일 스토리지',
  networks: '네트워크',
  'security-services': 'Security Service',

  // Containers
  containers: '컨테이너',
  clusters: '클러스터',
  k3s: 'Drover',

  // Database
  database: 'DATABASE',

  // Object Storage
  'object-storage': 'OBJECT STORAGE',
  buckets: '버킷',

  // Chat
  chat: 'Lumen',

  // Network
  network: '네트워크',
  routers: '라우터',
  'security-groups': '보안 그룹',
  loadbalancers: '로드밸런서',
  topology: '토폴로지',
  'floating-ips': 'Floating IP',
  ports: '포트',
  waygate: 'Waygate',

  // Library (Union Mount)
  library: '라이브러리',
  libraries: '라이브러리 관리',
  templates: '템플릿',

  // Project settings
  'project-settings': '프로젝트 설정',
  invitations: '초대',

  // Admin
  monitoring: '통합 모니터링',
  services: '서비스 상태',
  notion: 'Notion 연동',
  settings: '기본 설정',
  users: '사용자',
  projects: '프로젝트',
  quotas: '쿼터',
  groups: '그룹',
  roles: '역할',
  announcements: '공지 관리',
};

interface BreadcrumbResult {
  /** Short parent path, e.g. "COMPUTE / INSTANCES" */
  breadcrumb: string;
  /** Page title, e.g. "인스턴스" */
  title: string;
}

/**
 * Derives breadcrumb display strings from a URL pathname.
 * /dashboard/compute/instances → { breadcrumb: 'COMPUTE / INSTANCES', title: '인스턴스' }
 */
export function deriveBreadcrumb(pathname: string): BreadcrumbResult {
  // Strip leading slash and split
  const parts = pathname.replace(/^\//, '').split('/').filter(Boolean);

  // Strip the root mode segment (dashboard / admin)
  const relevant = parts.slice(1).filter(p => !isUuid(p) && p !== 'new');

  if (relevant.length === 0) {
    // /dashboard 또는 /admin 루트인 경우 첫 세그먼트로 타이틀 결정
    const root = parts[0];
    const rootTitle = ROUTE_LABELS[root] ?? root;
    return { breadcrumb: '', title: rootTitle };
  }

  const labels = relevant.map(p => {
    const label = ROUTE_LABELS[p];
    if (!label) return p.toUpperCase();
    return label.toUpperCase();
  });

  return {
    breadcrumb: labels.slice(0, -1).join(' / '),
    title: ROUTE_LABELS[relevant[relevant.length - 1]] ?? relevant[relevant.length - 1],
  };
}

function isUuid(s: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s) ||
    // also catch shorter hex-like IDs
    /^[0-9a-f]{32}$/i.test(s);
}
