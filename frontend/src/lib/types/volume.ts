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
