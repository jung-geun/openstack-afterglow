export interface SwiftContainer {
  name: string;
  count: number;
  bytes: number;
}

export interface AccountMeta {
  container_count: number;
  object_count: number;
  bytes_used: number;
}
export interface SwiftObject {
  name: string;
  bytes: number;
  content_type: string;
  last_modified: string;
  etag: string;
  is_dir?: boolean;
}

export interface SwiftObjectMeta extends SwiftObject {
  container: string;
  content_encoding?: string;
  content_disposition?: string;
  delete_at?: string;
}
