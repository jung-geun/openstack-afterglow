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
