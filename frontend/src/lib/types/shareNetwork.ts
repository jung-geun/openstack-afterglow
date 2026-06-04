export interface ShareNetwork {
  id: string;
  name: string;
  description: string;
  neutron_net_id: string | null;
  neutron_subnet_id: string | null;
  status: string;
  created_at: string | null;
}

export interface ShareNeutronNetwork {
  id: string;
  name: string;
  status: string;
  subnets: string[];
}

export interface ShareSubnet {
  id: string;
  name: string;
  cidr: string;
}
