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
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
}

export interface NetworkDetail {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
  subnet_details: SubnetDetail[];
  routers: RouterInfo[];
}
