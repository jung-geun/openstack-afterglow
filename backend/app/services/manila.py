"""
Manila CephFS 파일 스토리지 관리 서비스.

openstacksdk 는 Manila(Shared File Systems) API 를 manilaclient 로 래핑하지 않으므로
직접 REST 호출로 처리한다.
"""

import logging
import time

import httpx

from app.models.storage import FileStorageInfo

logger = logging.getLogger(__name__)


class ManilaClient:
    """Keystone 토큰 기반 Manila v2 REST 클라이언트."""

    def __init__(self, endpoint: str, token: str, project_id: str):
        # endpoint 예: http://manila.example.com:8786/v2/{project_id}
        self.base = endpoint.rstrip("/")
        self.headers = {
            "X-Auth-Token": token,
            "X-OpenStack-Manila-API-Version": "2.65",
            "Content-Type": "application/json",
        }
        self.project_id = project_id

    def _url(self, path: str) -> str:
        if self.base.endswith(self.project_id):
            return f"{self.base}/{path.lstrip('/')}"
        return f"{self.base}/{self.project_id}/{path.lstrip('/')}"

    def get(self, path: str, params: dict | None = None) -> dict:
        with httpx.Client() as c:
            r = c.get(self._url(path), headers=self.headers, params=params, timeout=30)
            r.raise_for_status()
            return r.json()

    def post(self, path: str, body: dict) -> dict:
        with httpx.Client() as c:
            url = self._url(path)
            logger.debug(f"Manila POST {url}")
            r = c.post(url, headers=self.headers, json=body, timeout=30)
            if not r.is_success:
                logger.error(f"Manila POST {url} → {r.status_code}: {r.text}")
            r.raise_for_status()
            return r.json()

    def put(self, path: str, body: dict) -> dict:
        with httpx.Client() as c:
            r = c.put(self._url(path), headers=self.headers, json=body, timeout=30)
            r.raise_for_status()
            return r.json()

    def delete(self, path: str) -> None:
        with httpx.Client() as c:
            r = c.delete(self._url(path), headers=self.headers, timeout=30)
            if r.status_code not in (200, 202, 204):
                r.raise_for_status()


def _normalize_manila_url(url: str) -> str:
    """Manila endpoint 가 /v1 으로 끝나면 /v2 로 치환.

    Manila v1 의 quota-sets 엔드포인트는 'os-quota-sets' 였고 v2 부터 'quota-sets' 로 변경됨.
    클라이언트는 마이크로버전 헤더(2.65)를 보내므로 v2 path 만 사용.
    """
    import re

    return re.sub(r"/v1(?=/|$)", "/v2", url)


def _get_manila_endpoint(conn) -> str:
    """openstacksdk connection 에서 Manila 엔드포인트 추출.
    OS_MANILA_ENDPOINT 환경변수로 오버라이드 가능.
    """
    from app.config import get_settings

    settings = get_settings()
    if getattr(settings, "os_manila_endpoint", ""):
        url = settings.os_manila_endpoint.rstrip("/")
        logger.debug(f"Manila endpoint (override): {url}")
        return _normalize_manila_url(url)

    # v2 우선: sharev2 → shared-file-system → share (v1 fallback)
    # Manila v1 catalog 에서 quota-sets 경로가 os-quota-sets 였으므로 v2 endpoint 우선 선택.
    for service_type in ("sharev2", "shared-file-system", "share"):
        for interface in ("public", "internal", "admin"):
            try:
                url = conn.endpoint_for(service_type, interface=interface)
                if url:
                    normalized = _normalize_manila_url(url.rstrip("/"))
                    logger.debug(f"Manila endpoint [{service_type}/{interface}]: {normalized}")
                    return normalized
            except Exception:
                continue
    raise RuntimeError("Manila 엔드포인트를 서비스 카탈로그에서 찾을 수 없습니다")


def get_client(conn) -> ManilaClient:
    # openstacksdk가 토큰을 재발급할 수 있으므로 원본 토큰/project_id 우선 사용
    token = getattr(conn, "_union_token", None) or conn.auth_token
    project_id = getattr(conn, "_union_project_id", None) or conn.current_project_id
    endpoint = _get_manila_endpoint(conn)
    logger.debug(
        f"Manila client: endpoint={endpoint}, project_id={project_id}, token_src={'original' if hasattr(conn, '_union_token') else 'sdk'}"
    )
    return ManilaClient(endpoint=endpoint, token=token, project_id=project_id)


# ---------------------------------------------------------------------------
# 파일 스토리지 관리
# ---------------------------------------------------------------------------


def get_file_storage_quota(conn) -> dict:
    """프로젝트의 Manila 할당량 (limit + in_use) 조회."""
    try:
        client = get_client(conn)
        project_id = getattr(conn, "_union_project_id", None) or conn.current_project_id
        data = client.get(f"quota-sets/{project_id}", params={"usage": "true"})
        quota = data.get("quota_set", {})

        def _q(key):
            v = quota.get(key, {})
            if isinstance(v, dict):
                return {"limit": v.get("limit", -1), "in_use": v.get("in_use", 0)}
            return {"limit": int(v) if v is not None else -1, "in_use": 0}

        result = {
            "shares": _q("shares"),
            "gigabytes": _q("gigabytes"),
            "share_networks": _q("share_networks"),
            "share_groups": _q("share_groups"),
            "snapshot_gigabytes": _q("snapshot_gigabytes"),
        }

        # Manila quota-sets가 in_use=0을 반환하더라도 실제 share가 있을 수 있음
        # (CephFS 백엔드나 quota enforcement 미활성 시 발생)
        if result["shares"]["in_use"] == 0:
            try:
                shares_data = client.get("shares/detail")
                actual_shares = shares_data.get("shares", [])
                if actual_shares:
                    result["shares"]["in_use"] = len(actual_shares)
                    total_gb = sum(int(s.get("size", 0)) for s in actual_shares)
                    if total_gb > 0 and result["gigabytes"]["in_use"] == 0:
                        result["gigabytes"]["in_use"] = total_gb
                    logger.debug(
                        "Manila quota fallback: %d shares, %d GB",
                        result["shares"]["in_use"],
                        result["gigabytes"]["in_use"],
                    )
            except Exception:
                logger.debug("Manila quota fallback 조회 실패", exc_info=True)

        return result
    except Exception:
        import logging as _logging

        _logging.getLogger(__name__).warning("Manila 파일 스토리지 quota 조회 실패", exc_info=True)
        return {
            k: {"limit": -1, "in_use": 0}
            for k in ["shares", "gigabytes", "share_networks", "share_groups", "snapshot_gigabytes"]
        }


def list_share_types(conn) -> list[dict]:
    """Manila에서 사용 가능한 share type 목록 조회."""
    client = get_client(conn)
    data = client.get("types")
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "is_default": t.get("share_type_access:is_public", True),
        }
        for t in data.get("share_types", [])
    ]


def list_share_networks(conn) -> list[dict]:
    """Manila에서 사용 가능한 share network 목록 조회."""
    client = get_client(conn)
    data = client.get("share-networks/detail")
    return [
        {
            "id": net["id"],
            "name": net.get("name", ""),
            "neutron_net_id": net.get("neutron_net_id"),
            "neutron_subnet_id": net.get("neutron_subnet_id"),
            "network_type": net.get("network_type"),
            "status": net.get("status", ""),
            "created_at": net.get("created_at"),
        }
        for net in data.get("share_networks", [])
    ]


def get_share_network(conn, share_network_id: str) -> dict:
    """Share network 상세 조회."""
    client = get_client(conn)
    data = client.get(f"share-networks/{share_network_id}")
    net = data.get("share_network", data)
    return {
        "id": net["id"],
        "name": net.get("name", ""),
        "description": net.get("description", ""),
        "neutron_net_id": net.get("neutron_net_id"),
        "neutron_subnet_id": net.get("neutron_subnet_id"),
        "network_type": net.get("network_type"),
        "status": net.get("status", ""),
        "created_at": net.get("created_at"),
        "security_service_ids": [ss.get("id", "") for ss in net.get("security_services", [])]
        if net.get("security_services")
        else [],
    }


def create_share_network(
    conn,
    name: str,
    neutron_net_id: str,
    neutron_subnet_id: str,
    description: str = "",
) -> dict:
    """Share network 생성."""
    client = get_client(conn)
    body = {
        "share_network": {
            "name": name,
            "description": description,
            "neutron_net_id": neutron_net_id,
            "neutron_subnet_id": neutron_subnet_id,
        }
    }
    return client.post("share-networks", body)["share_network"]


def delete_share_network(conn, share_network_id: str) -> None:
    """Share network 삭제."""
    client = get_client(conn)
    client.delete(f"share-networks/{share_network_id}")


def add_security_service_to_network(conn, share_network_id: str, security_service_id: str) -> dict:
    """Share network에 보안 서비스 연결."""
    client = get_client(conn)
    body = {"add_security_service": {"security_service_id": security_service_id}}
    return client.post(f"share-networks/{share_network_id}/action", body)


def remove_security_service_from_network(conn, share_network_id: str, security_service_id: str) -> dict:
    """Share network에서 보안 서비스 제거."""
    client = get_client(conn)
    body = {"remove_security_service": {"security_service_id": security_service_id}}
    return client.post(f"share-networks/{share_network_id}/action", body)


# ---------------------------------------------------------------------------
# Security Services
# ---------------------------------------------------------------------------


def list_security_services(conn) -> list[dict]:
    """Manila security service 목록 조회."""
    client = get_client(conn)
    data = client.get("security-services/detail")
    return [
        {
            "id": ss["id"],
            "name": ss.get("name", ""),
            "description": ss.get("description", ""),
            "type": ss.get("type", ""),
            "dns_ip": ss.get("dns_ip"),
            "server": ss.get("server"),
            "domain": ss.get("domain"),
            "status": ss.get("status", ""),
            "created_at": ss.get("created_at"),
        }
        for ss in data.get("security_services", [])
    ]


def create_security_service(
    conn,
    type: str,
    name: str,
    description: str = "",
    dns_ip: str = "",
    server: str = "",
    domain: str = "",
    user: str = "",
    password: str = "",
) -> dict:
    """Manila security service 생성."""
    client = get_client(conn)
    body: dict = {
        "type": type,
        "name": name,
    }
    if description:
        body["description"] = description
    if dns_ip:
        body["dns_ip"] = dns_ip
    if server:
        body["server"] = server
    if domain:
        body["domain"] = domain
    if user:
        body["user"] = user
    if password:
        body["password"] = password
    return client.post("security-services", {"security_service": body})["security_service"]


def delete_security_service(conn, security_service_id: str) -> None:
    """Manila security service 삭제."""
    client = get_client(conn)
    client.delete(f"security-services/{security_service_id}")


def create_file_storage(
    conn,
    name: str,
    size_gb: int,
    share_network_id: str,
    share_type: str = "cephfstype",
    share_proto: str = "CEPHFS",
    metadata: dict | None = None,
) -> FileStorageInfo:
    client = get_client(conn)
    share_body: dict = {
        "name": name,
        "share_proto": share_proto.upper(),
        "size": size_gb,
        "share_type": share_type,
        "metadata": metadata or {},
    }
    if share_network_id:
        share_body["share_network_id"] = share_network_id
    body = {"share": share_body}
    data = client.post("shares", body)["share"]
    file_storage_id = data["id"]

    # available 상태까지 폴링
    for _ in range(60):
        time.sleep(5)
        info = client.get(f"shares/{file_storage_id}")["share"]
        if info["status"] == "available":
            break
        if info["status"] == "error":
            raise RuntimeError(f"파일 스토리지 생성 실패 (error 상태): {file_storage_id}")

    return _parse_file_storage(client.get(f"shares/{file_storage_id}")["share"])


def delete_file_storage(conn, file_storage_id: str) -> None:
    client = get_client(conn)
    client.delete(f"shares/{file_storage_id}")


def list_file_storages(conn, metadata_filter: dict | None = None, all_tenants: bool = False) -> list[FileStorageInfo]:
    client = get_client(conn)
    params: dict = {}
    if all_tenants:
        params["all_tenants"] = "1"
    try:
        data = client.get("shares/detail", params=params or None)["shares"]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.warning(f"Manila shares/detail 400 (파일 스토리지 없음으로 추정): {e}")
            return []
        raise
    file_storages = [_parse_file_storage(s) for s in data]
    if metadata_filter:
        file_storages = [s for s in file_storages if all(s.metadata.get(k) == v for k, v in metadata_filter.items())]
    return file_storages


def get_file_storage(conn, file_storage_id: str) -> FileStorageInfo:
    client = get_client(conn)
    data = client.get(f"shares/{file_storage_id}")["share"]
    return _parse_file_storage(data)


# ---------------------------------------------------------------------------
# Access Rule (CephX)
# ---------------------------------------------------------------------------


def create_access_rule(
    conn,
    file_storage_id: str,
    access_to: str,
    access_level: str = "ro",  # "ro" | "rw"
    access_type: str = "cephx",  # "cephx" | "ip"
) -> dict:
    """
    접근 규칙 생성.
    - CephFS: access_type="cephx", access_to=cephx_id
    - NFS: access_type="ip", access_to=IP/CIDR
    반환: { access_id, access_key, access_to, access_level }
    """
    client = get_client(conn)
    body = {
        "allow_access": {
            "access_type": access_type,
            "access_to": access_to,
            "access_level": access_level,
        }
    }
    data = client.post(f"shares/{file_storage_id}/action", body)["access"]

    # access_key 조회 (CephX만 해당, IP 규칙은 없음)
    access_key = ""
    if access_type == "cephx":
        access_key = _get_access_key(client, file_storage_id, data["id"])
    return {
        "access_id": data["id"],
        "access_key": access_key,
        "access_to": access_to,
        "access_level": data["access_level"],
    }


def revoke_access_rule(conn, file_storage_id: str, access_id: str) -> None:
    client = get_client(conn)
    body = {"deny_access": {"access_id": access_id}}
    client.post(f"shares/{file_storage_id}/action", body)


def list_access_rules(conn, file_storage_id: str) -> list[dict]:
    client = get_client(conn)
    # API v2.45+: use share-access-rules endpoint instead of action
    data = client.get(f"share-access-rules?share_id={file_storage_id}")
    return data.get("access_rules", [])


def get_export_locations(conn, file_storage_id: str) -> list[str]:
    """CephFS export path 목록 반환 (예: '192.168.1.10:6789,... :/')."""
    client = get_client(conn)
    data = client.get(f"shares/{file_storage_id}/export_locations")
    locations = data.get("export_locations", [])
    return [loc["path"] for loc in locations if loc.get("is_admin_only") is False]


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------


def _get_access_key(client: ManilaClient, file_storage_id: str, access_id: str) -> str:
    """access rule 에서 CephX secret key 추출 (Manila API v2.45+)."""
    for _ in range(20):
        # API v2.45+: use share-access-rules endpoint
        data = client.get(f"share-access-rules?share_id={file_storage_id}")
        rules = data.get("access_rules", [])
        for rule in rules:
            if rule["id"] == access_id and rule.get("access_key"):
                return rule["access_key"]
        time.sleep(3)
    return ""


def _parse_file_storage(data: dict) -> FileStorageInfo:
    meta = data.get("metadata", {}) or {}
    locations = []
    for loc in data.get("export_locations", []):
        if isinstance(loc, dict):
            locations.append(loc.get("path", ""))
        elif isinstance(loc, str):
            locations.append(loc)

    share_proto = data.get("share_proto", "CEPHFS")

    # NFS export location: NFS 프로토콜인 경우 첫 번째 export 경로 사용
    nfs_export_location = None
    if share_proto == "NFS":
        nfs_export_location = locations[0] if locations else None

    return FileStorageInfo(
        id=data["id"],
        name=data.get("name", ""),
        status=data["status"],
        size=data["size"],
        share_proto=share_proto,
        export_locations=locations,
        metadata=meta,
        project_id=data.get("project_id"),
        created_at=str(data["created_at"]) if data.get("created_at") else None,
        nfs_export_location=nfs_export_location,
        library_name=meta.get("union_library"),
        library_version=meta.get("union_version"),
        built_at=meta.get("union_built_at"),
    )


# ---------------------------------------------------------------------------
# NFS access rule 관리
# ---------------------------------------------------------------------------


def ensure_nfs_access_rule(
    conn,
    file_storage_id: str,
    access_to: str,
    access_level: str = "rw",
) -> dict:
    """
    NFS access rule이 없으면 생성하고, 이미 있으면 기존 rule을 반환.
    access_to: IP 주소 또는 CIDR (예: "192.168.1.100" 또는 "10.0.0.0/24")
    """
    # 기존 access rule 조회
    existing_rules = list_access_rules(conn, file_storage_id)
    for rule in existing_rules:
        if (
            rule.get("access_type") == "ip"
            and rule.get("access_to") == access_to
            and rule.get("access_level") == access_level
            and rule.get("state") in ("active", "new")
        ):
            logger.info(f"NFS access rule 이미 존재: {access_to} ({rule.get('id')})")
            return {
                "access_id": rule["id"],
                "access_key": "",
                "access_to": access_to,
                "access_level": access_level,
            }

    # 새로 생성
    return create_access_rule(
        conn,
        file_storage_id=file_storage_id,
        access_to=access_to,
        access_level=access_level,
        access_type="ip",
    )


def set_share_public(conn, file_storage_id: str, is_public: bool = True) -> dict:
    """Manila share의 공개 범위 설정 (다른 프로젝트 접근 허용)."""
    client = get_client(conn)
    body = {"share": {"is_public": is_public}}
    return client.put(f"shares/{file_storage_id}", body)


def get_nfs_export_location(conn, file_storage_id: str) -> str | None:
    """NFS share의 export location을 반환. CephFS share이면 None."""
    info = get_file_storage(conn, file_storage_id)
    if info.share_proto != "NFS":
        return None
    locations = get_export_locations(conn, file_storage_id)
    return locations[0] if locations else None


# ---------------------------------------------------------------------------
# Manila share 메타데이터 관리
# ---------------------------------------------------------------------------


def update_share_metadata(conn, file_storage_id: str, metadata: dict) -> dict:
    """Manila share 메타데이터 업데이트."""
    client = get_client(conn)
    body = {"set_metadata": metadata}
    return client.post(f"shares/{file_storage_id}/metadata", body)


# ---------------------------------------------------------------------------
# Manila share snapshot 관리
# ---------------------------------------------------------------------------


def create_share_snapshot(
    conn,
    file_storage_id: str,
    name: str | None = None,
    description: str | None = None,
) -> dict:
    """Manila share 스냅샷 생성."""
    client = get_client(conn)
    body: dict = {"snapshot": {"share_id": file_storage_id}}
    if name:
        body["snapshot"]["name"] = name
    if description:
        body["snapshot"]["description"] = description
    return client.post("snapshots", body)["snapshot"]


def list_share_snapshots(conn, file_storage_id: str | None = None) -> list[dict]:
    """Manila share 스냅샷 목록 조회."""
    client = get_client(conn)
    params: dict = {}
    if file_storage_id:
        params["share_id"] = file_storage_id
    data = client.get("snapshots/detail", params=params or None)
    return data.get("snapshots", [])


def delete_share_snapshot(conn, snapshot_id: str) -> None:
    """Manila share 스냅샷 삭제."""
    client = get_client(conn)
    client.delete(f"snapshots/{snapshot_id}")


# ---------------------------------------------------------------------------
# 하위 호환 alias (기존 코드와 호환 유지)
# ---------------------------------------------------------------------------
get_share_quota = get_file_storage_quota
create_share = create_file_storage
delete_share = delete_file_storage
list_shares = list_file_storages
get_share = get_file_storage
