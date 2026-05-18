export interface ZunContainer {
  uuid: string;
  name: string;
  status: string;
  status_reason: string | null;
  image: string | null;
  command: string | null;
  cpu: number | null;
  memory: string | null;
  created_at: string | null;
}

export interface ContainerListResponse {
  items: ZunContainer[];
  service_available: boolean;
  message: string;
}

export interface EnvVar {
  key: string;
  value: string;
}

export interface PortMapping {
  container_port: number;
  host_port: number;
  protocol: string;
}
