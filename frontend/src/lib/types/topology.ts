import type { FloatingIpInfo } from '$lib/types/networks';

export interface SubnetDetail {
	id: string; name: string; cidr: string;
	gateway_ip: string | null; dhcp_enabled: boolean;
}
export interface TopologyNetwork {
	id: string; name: string; status: string;
	is_external: boolean; is_shared: boolean;
	project_id: string | null;
	subnet_details: SubnetDetail[];
}
export interface TopologyRouter {
	id: string; name: string; status: string;
	external_gateway_network_id: string | null;
	external_gateway_ips: string[];
	interface_ips: { ip_address: string; subnet_id: string }[];
	is_distributed: boolean;
	is_ha: boolean;
	connected_subnet_ids: string[];
	dvr_subnet_ids: string[];
	project_id: string | null;
}
export interface TopologyInstance {
	id: string; name: string; status: string;
	project_id?: string | null;
	network_names: string[];
	ip_addresses: { addr: string; type: string; network_name: string }[];
}
export interface TopologyLBMember {
	id: string; address: string; protocol_port: number;
	status: string; subnet_id: string | null; pool_id: string; server_id: string | null;
}
export interface TopologyLBListener {
	id: string; name: string; protocol: string; protocol_port: number;
	default_pool_id: string | null;
}
export interface TopologyLoadBalancer {
	id: string; name: string;
	vip_address: string | null; vip_port_id: string | null;
	vip_subnet_id: string | null; vip_network_id: string | null;
	provisioning_status: string; operating_status: string;
	project_id: string | null;
	listeners: TopologyLBListener[];
	members: TopologyLBMember[];
}
export interface TopologyData {
	networks: TopologyNetwork[];
	routers: TopologyRouter[];
	instances: TopologyInstance[];
	floating_ips: FloatingIpInfo[];
	load_balancers?: TopologyLoadBalancer[];
}
export interface TrafficRate { rx_bps: number; tx_bps: number; }
export interface TopologyTrafficInterface {
	instance_id: string;
	network_id: string;
	mac_address: string;
	rx_bps: number;
	tx_bps: number;
}
export interface TopologyTraffic {
	ts: number;
	instances: Record<string, TrafficRate>;
	networks: Record<string, TrafficRate>;
	routers: Record<string, TrafficRate>;
	load_balancers: Record<string, TrafficRate>;
	interfaces?: Record<string, TopologyTrafficInterface>;
	_meta?: { router_traffic?: string };
}
