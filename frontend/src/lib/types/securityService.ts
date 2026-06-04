export interface SecurityService {
  id: string;
  name: string;
  description: string;
  type: string;
  dns_ip: string | null;
  server: string | null;
  domain: string | null;
  status: string;
  created_at: string | null;
}

export interface ShareNetwork {
  id: string;
  name: string;
}

export const typeLabel: Record<string, string> = {
  ldap: 'LDAP',
  kerberos: 'Kerberos',
  active_directory: 'Active Directory',
};
