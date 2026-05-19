export interface Network {
  id: string;
  name: string;
  status?: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
}

export interface Router {
  id: string;
  name: string;
  status: string;
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
}

export type RouterListItem = Router;

export interface SubnetDetail {
  id: string;
  name: string;
  cidr: string;
  gateway_ip: string | null;
  dhcp_enabled: boolean;
}

export interface RouterInfo {
  id: string;
  name: string;
  status?: string;
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
}

export type NetworkRouterInfo = RouterInfo;

export interface NetworkDetail {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
  subnet_details: SubnetDetail[];
  routers: RouterInfo[];
  project_id?: string | null;
}

export interface FloatingIp {
  id: string;
  floating_ip_address: string;
  status: string;
  fixed_ip_address: string | null;
  port_id: string | null;
  instance_id?: string | null;
  instance_name?: string | null;
  project_id?: string | null;
  router_id?: string | null;
  floating_network_id?: string | null;
}

export type FloatingIpInfo = FloatingIp;
export type FloatingIpDetail = FloatingIp;

export interface AdminNetwork {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
  project_id?: string | null;
  project_name?: string;
}

export interface AdminRouter {
  id: string;
  name: string;
  status: string;
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
  project_id: string | null;
}

export interface NetworkInfo {
  id: string;
  name: string;
  is_external?: boolean;
  is_shared?: boolean;
}

export interface PortInfo {
  id: string;
  name: string | null;
  status: string;
  device_owner: string | null;
  fixed_ips: { ip_address: string }[];
  project_id: string | null;
  security_group_ids?: string[];
  mac_address?: string;
  network_id?: string;
}

export const networkStatusColor: Record<string, string> = {
  ACTIVE: 'text-green-400 bg-green-900/30',
  DOWN: 'text-red-400 bg-red-900/30',
  BUILD: 'text-yellow-400 bg-yellow-900/30',
};
