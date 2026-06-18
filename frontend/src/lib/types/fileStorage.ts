export interface ExportLocationDetail {
  path: string;
  preferred: boolean;
  share_instance_id: string | null;
}

export interface FileStorage {
  id: string;
  name: string;
  status: string;
  size: number;
  share_proto: string;
  export_locations: string[];
  metadata: Record<string, string>;
  project_id: string | null;
  created_at: string | null;
  is_public: boolean;
  library_name: string | null;
  library_version: string | null;
  built_at: string | null;
  // 확장 필드
  progress: string | null;
  user_id: string | null;
  user_name: string | null;
  access_rules_status: string | null;
  host: string | null;
  availability_zone: string | null;
  share_type_name: string | null;
  share_network_id: string | null;
  export_location_details: ExportLocationDetail[];
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
