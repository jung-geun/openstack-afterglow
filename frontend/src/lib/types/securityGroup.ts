export interface SecurityGroupRule {
	id: string;
	direction: string;
	protocol: string | null;
	port_range_min: number | null;
	port_range_max: number | null;
	remote_ip_prefix: string | null;
	ethertype: string;
}

export interface SecurityGroup {
	id: string;
	name: string;
	description: string;
	rules: SecurityGroupRule[];
}
