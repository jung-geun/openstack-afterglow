// WireGuard VPN 게이트웨이 타입 — backend/app/models/vpn.py 응답과 정확히 일치시킨다.

export interface VpnServer {
	id: string;
	project_id: string;
	name: string;
	status: string;
	status_reason: string | null;
	server_vm_id: string | null;
	endpoint_ip: string | null;
	listen_port: number;
	tunnel_cidr: string;
	dns: string | null;
	mtu: number | null;
	server_public_key: string | null;
	created_at: string | null;
	updated_at: string | null;
	// Redis 최신 상태 병합 (에이전트가 마지막으로 보고한 시각/피어 수)
	last_status_reported_at: string | null;
	peer_count: number | null;
}

export interface VpnClient {
	id: string;
	server_id: string;
	project_id: string;
	name: string;
	enabled: boolean;
	public_key: string;
	tunnel_ip: string;
	allowed_ips: string[];
	dns: string | null;
	created_at: string | null;
	updated_at: string | null;
	// Redis 상태 병합
	online: boolean | null;
	last_handshake_at: string | null;
	rx_bytes: number | null;
	tx_bytes: number | null;
}

/** 클라이언트 발급 직후 1회 응답 — 평문 .conf 를 포함한다. */
export interface VpnClientCreateResult extends VpnClient {
	tunnel_conf: string;
}

export interface VpnClientCreateRequest {
	name: string;
	allowed_ips?: string[];
	dns?: string;
}

export interface VpnClientUpdateRequest {
	name?: string;
	enabled?: boolean;
}
