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

export type FileStorageDeleteRootCauseCode =
  | 'dhss_false_share_network_mismatch'
  | 'backend_missing_after_failed_create_or_delete'
  | 'normal_delete_possible'
  | 'unknown';

export interface FileStorageDeleteDiagnostic {
  file_storage_id: string;
  status: string | null;
  share_proto: string | null;
  share_type_name: string | null;
  share_network_id: string | null;
  share_instance_ids: string[];
  root_cause_code: FileStorageDeleteRootCauseCode;
  confidence: 'high' | 'medium' | 'low';
  summary: string;
  evidence: string[];
  recommended_action: string;
  force_delete_available: boolean;
}

export interface FileStorageForceDeleteResult {
  file_storage_id: string;
  status: 'force_delete_submitted' | 'already_deleted';
  diagnostic: FileStorageDeleteDiagnostic | null;
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
