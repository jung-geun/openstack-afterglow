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
