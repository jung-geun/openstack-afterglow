// Afterglow route label map
// URL path segment → Korean/English display label
// Used to auto-derive breadcrumbs in TopBar from $page.url.pathname

export const ROUTE_LABELS: Record<string, string> = {
  // Top level
  dashboard: '대시보드',
  admin: 'ADMIN',

  // Overview
  'my-resources': '내 리소스',

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
  manage: '라이브러리 관리',
  networks: '네트워크',
  'security-services': 'Security Service',

  // Containers
  containers: '컨테이너',
  clusters: '클러스터',
  k3s: 'k3s 클러스터',

  // Database
  database: 'DATABASE',

  // Object Storage
  'object-storage': 'OBJECT STORAGE',

  // Network
  network: '네트워크',
  routers: '라우터',
  'security-groups': '보안 그룹',
  loadbalancers: '로드밸런서',
  topology: '토폴로지',
  'floating-ips': 'Floating IP',
  ports: '포트',

  // Admin
  monitoring: '통합 모니터링',
  services: '서비스 상태',
  notion: 'Notion 연동',
  users: '사용자',
  projects: '프로젝트',
  quotas: '쿼터',
  groups: '그룹',
  roles: '역할',
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
    return { breadcrumb: '', title: '대시보드' };
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
