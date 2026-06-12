export interface LibraryConfig {
  id: string;
  name: string;
  version: string;
  packages: string[];
  depends_on: string[];
  available_prebuilt: boolean;
  share_proto: string;
  visibility: string;
  license_type?: string | null;
  max_concurrent_mounts?: number | null;
}

export interface FileStorage {
  id: string;
  name: string;
  status: string;
  library_name: string | null;
  library_version: string | null;
  metadata: Record<string, string>;
}

export interface LibraryBuild {
  id: number;
  library_id: string;
  file_storage_id: string;
  server_id: string | null;
  status: string;
  cloud_init_status: string | null;
  progress_step: string;
  progress_pct: number;
  error_message: string | null;
  console_log_excerpt: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

export interface LibraryBuildDetail extends LibraryBuild {
  vm_status: string | null;
  vm_ip: string | null;
  live_console: string | null;
  console_note: string | null;
}

export interface TsPoint { ts: number; [key: string]: number | undefined; }

export interface GraphNode {
  id: string;
  name: string;
  level: number;
  posX: number;
  posY: number;
  status: string;
}

export interface GraphEdge { from: string; to: string; }
