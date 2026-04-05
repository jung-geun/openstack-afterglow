"""
Manila CephFS share 관리 서비스.

openstacksdk 는 Manila(Shared File Systems) API 를 manilaclient 로 래핑하지 않으므로
직접 REST 호출로 처리한다.
"""
import logging
import time
import httpx
from typing import Optional

from app.models.storage import ShareInfo

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

    def get(self, path: str) -> dict:
        with httpx.Client() as c:
            r = c.get(self._url(path), headers=self.headers, timeout=30)
            r.raise_for_status()
            return r.json()

    def post(self, path: str, body: dict) -> dict:
        with httpx.Client() as c:
            url = self._url(path)
            logger.warning(f"Manila POST {url} body={body}")
            r = c.post(url, headers=self.headers, json=body, timeout=30)
            if not r.is_success:
                logger.error(f"Manila POST {url} → {r.status_code}: {r.text}")
            r.raise_for_status()
            return r.json()

    def delete(self, path: str) -> None:
        with httpx.Client() as c:
            r = c.delete(self._url(path), headers=self.headers, timeout=30)
            if r.status_code not in (200, 202, 204):
                r.raise_for_status()


def _get_manila_endpoint(conn) -> str:
    """openstacksdk connection 에서 Manila 엔드포인트 추출.
    OS_MANILA_ENDPOINT 환경변수로 오버라이드 가능.
    """
    from app.config import get_settings
    settings = get_settings()
    if getattr(settings, "os_manila_endpoint", ""):
        url = settings.os_manila_endpoint.rstrip("/")
        logger.warning(f"Manila endpoint (override): {url}")
        return url

    for service_type in ("share", "sharev2", "shared-file-system"):
        for interface in ("public", "internal", "admin"):
            try:
                url = conn.endpoint_for(service_type, interface=interface)
                if url:
                    logger.warning(f"Manila endpoint [{service_type}/{interface}]: {url}")
                    return url.rstrip("/")
            except Exception:
                continue
    raise RuntimeError("Manila 엔드포인트를 서비스 카탈로그에서 찾을 수 없습니다")


def get_client(conn) -> ManilaClient:
    # openstacksdk가 토큰을 재발급할 수 있으므로 원본 토큰/project_id 우선 사용
    token = getattr(conn, "_union_token", None) or conn.auth_token
    project_id = getattr(conn, "_union_project_id", None) or conn.current_project_id
    endpoint = _get_manila_endpoint(conn)
    logger.warning(f"Manila client: endpoint={endpoint}, project_id={project_id}, token_src={'original' if hasattr(conn, '_union_token') else 'sdk'}")
    return ManilaClient(endpoint=endpoint, token=token, project_id=project_id)


# ---------------------------------------------------------------------------
# Share 관리
# ---------------------------------------------------------------------------

def get_share_quota(conn) -> dict:
    """프로젝트의 Manila 할당량 (limit + in_use) 조회."""
    try:
        client = get_client(conn)
        project_id = getattr(conn, "_union_project_id", None) or conn.current_project_id
        data = client.get(f"quota-sets/{project_id}?usage=true")
        quota = data.get("quota_set", {})

        def _q(key):
            v = quota.get(key, {})
            if isinstance(v, dict):
                return {"limit": v.get("limit", -1), "in_use": v.get("in_use", 0)}
            return {"limit": int(v) if v is not None else -1, "in_use": 0}

        return {
            "shares": _q("shares"),
            "gigabytes": _q("gigabytes"),
            "share_networks": _q("share_networks"),
            "share_groups": _q("share_groups"),
            "snapshot_gigabytes": _q("snapshot_gigabytes"),
        }
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).warning("Manila share quota 조회 실패", exc_info=True)
        return {k: {"limit": -1, "in_use": 0} for k in ["shares", "gigabytes", "share_networks", "share_groups", "snapshot_gigabytes"]}


def create_share(
    conn,
    name: str,
    size_gb: int,
    share_network_id: str,
    share_type: str = "cephfstype",
    metadata: Optional[dict] = None,
) -> ShareInfo:
    client = get_client(conn)
    share_body: dict = {
        "name": name,
        "share_proto": "CEPHFS",
        "size": size_gb,
        "share_type": share_type,
        "metadata": metadata or {},
    }
    if share_network_id:
        share_body["share_network_id"] = share_network_id
    body = {"share": share_body}
    data = client.post("shares", body)["share"]
    share_id = data["id"]

    # available 상태까지 폴링
    for _ in range(60):
        time.sleep(5)
        info = client.get(f"shares/{share_id}")["share"]
        if info["status"] == "available":
            break
        if info["status"] == "error":
            raise RuntimeError(f"Share 생성 실패 (error 상태): {share_id}")

    return _parse_share(client.get(f"shares/{share_id}")["share"])


def delete_share(conn, share_id: str) -> None:
    client = get_client(conn)
    client.delete(f"shares/{share_id}")


def list_shares(conn, metadata_filter: Optional[dict] = None) -> list[ShareInfo]:
    client = get_client(conn)
    try:
        data = client.get("shares/detail")["shares"]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.warning(f"Manila shares/detail 400 (shares 없음으로 추정): {e}")
            return []
        raise
    shares = [_parse_share(s) for s in data]
    if metadata_filter:
        shares = [
            s for s in shares
            if all(s.metadata.get(k) == v for k, v in metadata_filter.items())
        ]
    return shares


def get_share(conn, share_id: str) -> ShareInfo:
    client = get_client(conn)
    data = client.get(f"shares/{share_id}")["share"]
    return _parse_share(data)


# ---------------------------------------------------------------------------
# Access Rule (CephX)
# ---------------------------------------------------------------------------

def create_access_rule(
    conn,
    share_id: str,
    cephx_id: str,
    access_level: str = "ro",   # "ro" | "rw"
) -> dict:
    """
    CephX access rule 생성.
    반환: { access_id, access_key, cephx_id }
    """
    client = get_client(conn)
    body = {
        "allow_access": {
            "access_type": "cephx",
            "access_to": cephx_id,
            "access_level": access_level,
        }
    }
    data = client.post(f"shares/{share_id}/action", body)["access"]

    # access_key 조회 (API v2.21+)
    access_key = _get_access_key(client, share_id, data["id"])
    return {
        "access_id": data["id"],
        "access_key": access_key,
        "cephx_id": cephx_id,
        "access_level": data["access_level"],
    }


def revoke_access_rule(conn, share_id: str, access_id: str) -> None:
    client = get_client(conn)
    body = {"deny_access": {"access_id": access_id}}
    client.post(f"shares/{share_id}/action", body)


def list_access_rules(conn, share_id: str) -> list[dict]:
    client = get_client(conn)
    # API v2.45+: use share-access-rules endpoint instead of action
    data = client.get(f"share-access-rules?share_id={share_id}")
    return data.get("access_rules", [])


def get_export_locations(conn, share_id: str) -> list[str]:
    """CephFS export path 목록 반환 (예: '192.168.1.10:6789,... :/')."""
    client = get_client(conn)
    data = client.get(f"shares/{share_id}/export_locations")
    locations = data.get("export_locations", [])
    return [loc["path"] for loc in locations if loc.get("is_admin_only") is False]


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------

def _get_access_key(client: ManilaClient, share_id: str, access_id: str) -> str:
    """access rule 에서 CephX secret key 추출 (Manila API v2.45+)."""
    for _ in range(20):
        # API v2.45+: use share-access-rules endpoint
        data = client.get(f"share-access-rules?share_id={share_id}")
        rules = data.get("access_rules", [])
        for rule in rules:
            if rule["id"] == access_id and rule.get("access_key"):
                return rule["access_key"]
        time.sleep(3)
    return ""


def _parse_share(data: dict) -> ShareInfo:
    meta = data.get("metadata", {}) or {}
    locations = []
    for loc in data.get("export_locations", []):
        if isinstance(loc, dict):
            locations.append(loc.get("path", ""))
        elif isinstance(loc, str):
            locations.append(loc)

    return ShareInfo(
        id=data["id"],
        name=data.get("name", ""),
        status=data["status"],
        size=data["size"],
        share_proto=data.get("share_proto", "CEPHFS"),
        export_locations=locations,
        metadata=meta,
        library_name=meta.get("union_library"),
        library_version=meta.get("union_version"),
        built_at=meta.get("union_built_at"),
    )
