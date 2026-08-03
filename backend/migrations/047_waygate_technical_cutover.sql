-- Waygate replaces the retired VPN service namespace.
-- The deployment preflight guarantees there are no active VPN gateways or clients.
DROP TABLE IF EXISTS vpn_network_attachments;
DROP TABLE IF EXISTS vpn_clients;
DROP TABLE IF EXISTS vpn_servers;

CREATE TABLE IF NOT EXISTS waygate_servers (
  id CHAR(36) NOT NULL,
  project_id VARCHAR(64) NOT NULL,
  name VARCHAR(63) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'CREATING',
  status_reason TEXT NULL,
  server_vm_id VARCHAR(64) NULL,
  flavor_id VARCHAR(64) NULL,
  provider_network_id VARCHAR(64) NULL,
  provider_port_id VARCHAR(64) NULL,
  security_group_id VARCHAR(64) NULL,
  fip_id VARCHAR(64) NULL,
  endpoint_ip VARCHAR(45) NULL,
  key_name VARCHAR(255) NULL,
  server_public_key VARCHAR(64) NULL,
  listen_port INT NOT NULL DEFAULT 51820,
  tunnel_cidr VARCHAR(43) NOT NULL DEFAULT '10.8.0.0/24',
  dns VARCHAR(255) NULL,
  mtu INT NULL,
  created_by_user_id VARCHAR(64) NULL,
  created_by_username VARCHAR(255) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  deleted_at DATETIME(6) NULL,
  deleted_by_user_id VARCHAR(64) NULL,
  deleted_reason VARCHAR(255) NULL,
  PRIMARY KEY (id),
  KEY idx_waygate_server_project_created (project_id, created_at),
  KEY ix_waygate_servers_project_id (project_id),
  KEY ix_waygate_servers_created_by_user_id (created_by_user_id),
  KEY ix_waygate_servers_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS waygate_clients (
  id CHAR(36) NOT NULL,
  server_id CHAR(36) NOT NULL,
  project_id VARCHAR(64) NOT NULL,
  name VARCHAR(63) NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  public_key VARCHAR(64) NOT NULL,
  private_key_encrypted TEXT NOT NULL,
  preshared_key_encrypted TEXT NULL,
  tunnel_ip VARCHAR(45) NULL,
  allowed_ips JSON NULL,
  dns VARCHAR(255) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  deleted_at DATETIME(6) NULL,
  deleted_by_user_id VARCHAR(64) NULL,
  deleted_reason VARCHAR(255) NULL,
  PRIMARY KEY (id),
  CONSTRAINT uq_waygate_client_server_tunnel_ip UNIQUE (server_id, tunnel_ip),
  CONSTRAINT uq_waygate_client_server_name UNIQUE (server_id, name),
  CONSTRAINT fk_waygate_clients_server FOREIGN KEY (server_id) REFERENCES waygate_servers(id) ON DELETE CASCADE,
  KEY idx_waygate_client_project_created (project_id, created_at),
  KEY ix_waygate_clients_server_id (server_id),
  KEY ix_waygate_clients_project_id (project_id),
  KEY ix_waygate_clients_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS waygate_network_attachments (
  id INT NOT NULL AUTO_INCREMENT,
  server_id CHAR(36) NOT NULL,
  project_id VARCHAR(64) NOT NULL,
  network_id VARCHAR(64) NOT NULL,
  subnet_id VARCHAR(64) NULL,
  port_id VARCHAR(64) NULL,
  cidr VARCHAR(43) NULL,
  nat_mode VARCHAR(16) NOT NULL DEFAULT 'snat',
  status VARCHAR(20) NOT NULL DEFAULT 'CREATING',
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_waygate_network_attachments_server FOREIGN KEY (server_id) REFERENCES waygate_servers(id) ON DELETE CASCADE,
  KEY idx_waygate_netattach_server (server_id),
  KEY ix_waygate_network_attachments_server_id (server_id),
  KEY ix_waygate_network_attachments_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
