export interface Volume {
  id: string;
  name: string;
  status: string;
  size: number;
  volume_type: string | null;
  attachments: Record<string, unknown>[];
  bootable?: boolean;
  volume_image_metadata?: Record<string, string> | null;
}

export interface VolumeBackup {
  id: string;
  name: string;
  description: string | null;
  volume_id: string;
  status: string;
  size: number;
  created_at: string | null;
  is_incremental: boolean;
  has_dependent_backups: boolean;
}

export interface Snapshot {
  id: string;
  name: string;
  status: string;
  volume_id: string;
  size: number;
  description: string;
  created_at: string | null;
}

export interface VolumeSnapshot {
  id: string;
  name: string;
  status: string;
  volume_id: string;
  size: number;
  description: string;
  created_at: string | null;
  project_id?: string;
}

export interface AdminVolume {
  id: string;
  name: string;
  status: string;
  size: number;
  project_id: string | null;
  created_at: string | null;
  bootable?: boolean;
  project_name?: string;
}

export interface AdminVolumeStatusCount {
  status: string;
  count: number;
}

export interface AdminVolumeStatusSummary {
  total: number;
  statuses: AdminVolumeStatusCount[];
}

export interface AdminVolumeDetail {
  id: string;
  name: string;
  status: string;
  size: number;
  volume_type: string;
  project_id: string | null;
  attachments: { server_id: string; device: string; id: string }[];
  created_at: string | null;
  description: string;
  bootable: boolean | null;
  encrypted: boolean | null;
  multiattach: boolean | null;
  metadata: Record<string, string>;
}

export type VolumeDeleteRootCause =
  | 'already_deleted'
  | 'attached_volume_delete_blocked'
  | 'dependent_snapshot_or_backup'
  | 'recoverable_error_deleting'
  | 'recoverable_error_state'
  | 'normal_delete_possible'
  | 'not_recoverable_status'
  | 'unknown';

export type VolumeDeleteRecoveryStatus =
  | 'deleted'
  | 'already_deleted'
  | 'delete_submitted'
  | 'blocked'
  | 'failed';

export type VolumeDeleteRecoveryAction =
  | 'diagnose'
  | 'reset_status'
  | 'delete'
  | 'verify_after_delete'
  | 'force_delete'
  | 'verify_after_force_delete';

export type VolumeDeleteRecoveryStepStatus = 'success' | 'skipped' | 'failed';

export interface VolumeDeleteMessage {
  id: string | null;
  event_id: string | null;
  request_id: string | null;
  message_level: string | null;
  resource_uuid: string | null;
  resource_type: string | null;
  user_message: string | null;
  created_at: string | null;
}

export interface VolumeDeleteDependency {
  id: string;
  status: string | null;
  name: string | null;
  kind: 'snapshot' | 'backup';
}

export interface VolumeDeleteDiagnostic {
  volume_id: string;
  status: string | null;
  project_id: string | null;
  attachments: Record<string, unknown>[];
  dependencies: VolumeDeleteDependency[];
  messages: VolumeDeleteMessage[];
  root_cause_code: VolumeDeleteRootCause;
  confidence: 'high' | 'medium' | 'low';
  summary: string;
  evidence: string[];
  recommended_action: string;
  recovery_available: boolean;
  force_delete_available: boolean;
}

export interface VolumeDeleteRecoveryStep {
  action: VolumeDeleteRecoveryAction;
  status: VolumeDeleteRecoveryStepStatus;
  detail: string | null;
}

export interface VolumeDeleteRecoveryResult {
  volume_id: string;
  status: VolumeDeleteRecoveryStatus;
  verified_deleted: boolean;
  final_status: string | null;
  diagnostic: VolumeDeleteDiagnostic;
  steps: VolumeDeleteRecoveryStep[];
}
