export interface FileStorage {
  id: string;
  name: string;
  status: string;
  size: number;
  share_proto: string;
  export_locations: string[];
  metadata: Record<string, string>;
  library_name: string | null;
  library_version: string | null;
  built_at: string | null;
}

export interface AccessRule {
  id: string;
  access_to: string;
  access_level: string;
  access_type?: string;
  state: string;
  access_key?: string;
}

export interface ShareSnapshot {
  id: string;
  name: string;
  status: string;
  share_id: string;
  size: number;
  description: string | null;
  created_at: string | null;
}

export interface AdminFileStorage {
  id: string;
  name: string;
  status: string;
  size: number;
  share_proto: string;
  metadata: Record<string, string>;
  project_id: string | null;
  created_at: string | null;
  export_locations: string[];
}
