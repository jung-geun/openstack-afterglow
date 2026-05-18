export interface LayerInfo {
  id: string;
  name: string;
  version: string;
  created_at: string;
  created_by: string;
  sealed: boolean;
  parent_id: string | null;
  ubuntu_base: string | null;
  build_recipe: Record<string, unknown>;
  installed_packages: Record<string, unknown>;
  content_hash: string;
  size_bytes: number | null;
  file_count: number | null;
}

export interface AncestorChain {
  layers: LayerInfo[];
}

export function formatLayerSize(bytes: number | null): string {
  if (bytes === null) return '-';
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

export function formatLayerDate(dt: string): string {
  return new Date(dt).toLocaleString('ko-KR');
}

export function layerHref(id: string): string {
  return `/dashboard/library/${encodeURIComponent(id)}`;
}
