"""Trove (Database as a Service) 서비스 래퍼.

openstacksdk의 conn.database 프록시를 사용.
서비스가 없거나 오류 시 빈 목록/0을 반환하여 optional 서비스로 동작.
"""

import logging

_logger = logging.getLogger(__name__)


def _instance_to_dict(i) -> dict:
    flavor = getattr(i, "flavor", {}) or {}
    volume = getattr(i, "volume", {}) or {}
    links = getattr(i, "links", []) or []
    # hostname / ip 추출: links 또는 addresses 에서 시도
    hostname = getattr(i, "hostname", None) or ""
    addresses = getattr(i, "addresses", {}) or {}
    ip = ""
    if not hostname and addresses:
        for net_addrs in addresses.values():
            if net_addrs:
                ip = net_addrs[0].get("addr", "") if isinstance(net_addrs[0], dict) else ""
                break
    return {
        "id": i.id,
        "name": i.name or "",
        "status": i.status or "",
        "datastore": getattr(i, "datastore", {}) or {},
        "flavor_id": flavor.get("id", "") if isinstance(flavor, dict) else "",
        "flavor_ram": flavor.get("ram", 0) if isinstance(flavor, dict) else 0,
        "size": volume.get("size", 0) if isinstance(volume, dict) else 0,
        "created_at": str(getattr(i, "created_at", "") or ""),
        "hostname": hostname,
        "ip": ip,
        "links": [lk.get("href", "") if isinstance(lk, dict) else str(lk) for lk in links],
    }


def list_instances(conn) -> list[dict]:
    """현재 프로젝트의 DB 인스턴스 목록 반환."""
    try:
        return [_instance_to_dict(i) for i in conn.database.instances()]
    except Exception:
        _logger.debug("Trove 인스턴스 목록 조회 실패", exc_info=True)
        return []


def count_instances(conn) -> int:
    """현재 프로젝트의 DB 인스턴스 수 반환."""
    try:
        return sum(1 for _ in conn.database.instances())
    except Exception:
        return 0


def get_instance(conn, instance_id: str) -> dict:
    """DB 인스턴스 상세 정보 반환."""
    i = conn.database.get_instance(instance_id)
    return _instance_to_dict(i)


def create_instance(
    conn,
    name: str,
    flavor_id: str,
    volume_size: int,
    datastore_type: str,
    datastore_version: str,
    databases: list | None = None,
    users: list | None = None,
    restore_backup_id: str | None = None,
    availability_zone: str | None = None,
    volume_type: str | None = None,
    nics: list[str] | None = None,
    locality: str | None = None,
    configuration_id: str | None = None,
    replica_of: str | None = None,
    replica_count: int | None = None,
) -> dict:
    """DB 인스턴스 생성 (raw REST 방식으로 안정성 확보)."""
    if locality and not (replica_of or replica_count):
        _logger.warning("locality=%s 무시: replica context 없음 (standalone 인스턴스)", locality)
        locality = None

    instance_body: dict = {
        "name": name,
        "flavorRef": flavor_id,
        "volume": {"size": volume_size},
    }
    if volume_type:
        instance_body["volume"]["type"] = volume_type
    if datastore_type:
        instance_body["datastore"] = {"type": datastore_type, "version": datastore_version}
    if availability_zone:
        instance_body["availability_zone"] = availability_zone
    if nics:
        instance_body["nics"] = [{"net-id": nid} for nid in nics]
    if locality:
        instance_body["locality"] = locality
    if databases:
        instance_body["databases"] = [{"name": db} for db in databases]
    if users:
        instance_body["users"] = users
    if configuration_id:
        instance_body["configuration"] = configuration_id
    if restore_backup_id:
        instance_body["restorePoint"] = {"backupRef": restore_backup_id}
    if replica_of:
        instance_body["replica_of"] = replica_of
        if replica_count:
            instance_body["replica_count"] = replica_count

    payload = {"instance": instance_body}
    _logger.debug("Trove create_instance payload: %s", payload)

    resp = conn.database.post("/instances", json=payload)
    status = getattr(resp, "status_code", None)
    text = (getattr(resp, "text", "") or "")[:2000]
    _logger.debug("Trove create_instance response: status=%s body=%s", status, text)

    body = resp.json() if hasattr(resp, "json") else {}
    instance_data = body.get("instance")
    if not instance_data or not instance_data.get("id"):
        fault = body.get("instanceFault") or {}
        fault_msg = str(fault.get("message", "") or "")
        import re as _re
        m = _re.search(r"\(([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\)", fault_msg)
        fault_id = m.group(1) if m else ""
        _logger.error(
            "Trove create_instance 실패 status=%s payload_keys=%s fault_id=%s body=%s",
            status, list(instance_body.keys()), fault_id, text,
        )
        raise RuntimeError(
            f"Trove 생성 실패 (HTTP {status})"
            + (f" — Trove fault ID: {fault_id}" if fault_id else "")
            + (f" — {fault_msg[:200]}" if fault_msg else "")
        )

    return {
        "id": instance_data.get("id", ""),
        "name": instance_data.get("name", ""),
        "status": instance_data.get("status", ""),
        "datastore": instance_data.get("datastore", {}),
        "flavor_id": (instance_data.get("flavor") or {}).get("id", flavor_id),
        "flavor_ram": (instance_data.get("flavor") or {}).get("ram", 0),
        "size": (instance_data.get("volume") or {}).get("size", volume_size),
        "created_at": str(instance_data.get("created", "") or ""),
        "hostname": instance_data.get("hostname", "") or "",
        "ip": "",
        "links": [],
    }


def delete_instance(conn, instance_id: str) -> None:
    """DB 인스턴스 삭제."""
    conn.database.delete_instance(instance_id, ignore_missing=False)


def restart_instance(conn, instance_id: str) -> None:
    """DB 인스턴스 재시작."""
    i = conn.database.get_instance(instance_id)
    i.restart(conn.database)


def enable_root(conn, instance_id: str) -> dict:
    """root 유저 활성화. {name, password} 반환."""
    i = conn.database.get_instance(instance_id)
    result = i.enable_root_user(conn.database)
    if isinstance(result, dict):
        return result
    # result 가 Resource 객체일 수 있음
    return {
        "name": getattr(result, "name", "root"),
        "password": getattr(result, "password", ""),
    }


# ---------------------------------------------------------------------------
# 데이터베이스 (인스턴스 내부) 관리
# ---------------------------------------------------------------------------


def list_databases(conn, instance_id: str) -> list[dict]:
    """인스턴스 내 데이터베이스 목록."""
    try:
        return [
            {
                "name": db.name or "",
                "character_set": getattr(db, "character_set", "utf8") or "utf8",
                "collate": getattr(db, "collate", "") or "",
            }
            for db in conn.database.databases(instance_id)
        ]
    except Exception:
        _logger.debug("Trove DB 목록 조회 실패 instance=%s", instance_id, exc_info=True)
        return []


def create_database(
    conn, instance_id: str, name: str, character_set: str = "utf8", collate: str = "utf8_general_ci"
) -> None:
    """인스턴스 내 데이터베이스 생성."""
    conn.database.create_database(instance_id, name=name, character_set=character_set, collate=collate)


def delete_database(conn, instance_id: str, db_name: str) -> None:
    """인스턴스 내 데이터베이스 삭제."""
    conn.database.delete_database(db_name, instance=instance_id, ignore_missing=False)


# ---------------------------------------------------------------------------
# 유저 (인스턴스 내부) 관리
# ---------------------------------------------------------------------------


def list_users(conn, instance_id: str) -> list[dict]:
    """인스턴스 내 유저 목록."""
    try:
        return [
            {
                "name": u.name or "",
                "databases": getattr(u, "databases", []) or [],
            }
            for u in conn.database.users(instance_id)
        ]
    except Exception:
        _logger.debug("Trove 유저 목록 조회 실패 instance=%s", instance_id, exc_info=True)
        return []


def create_user(conn, instance_id: str, name: str, password: str, databases: list[str] | None = None) -> None:
    """인스턴스 내 유저 생성."""
    user_body: dict = {"name": name, "password": password}
    if databases:
        user_body["databases"] = [{"name": db} for db in databases]
    conn.database.create_user(instance_id, **user_body)


def delete_user(conn, instance_id: str, username: str) -> None:
    """인스턴스 내 유저 삭제."""
    conn.database.delete_user(username, instance=instance_id, ignore_missing=False)


# ---------------------------------------------------------------------------
# 플레이버 / 데이터스토어
# ---------------------------------------------------------------------------


_ALLOWED_DB_FLAVORS = {"cpu.2c_2g", "cpu.4c_8g", "cpu.8c_16g", "cpu.8c_32g"}


def list_flavors(conn) -> list[dict]:
    """DB 플레이버 목록 (허용된 flavor만 반환).

    openstacksdk Flavor ORM 이 일부 환경에서 id 를 None 으로 반환해
    flavorRef 에 name 이 전송되는 문제 → raw REST 로 숫자 id 를 직접 파싱.
    """
    try:
        resp = conn.database.get("/flavors")
        body = resp.json() if hasattr(resp, "json") else {}
        result: list[dict] = []
        for f in body.get("flavors", []):
            name = f.get("name", "") or ""
            if name not in _ALLOWED_DB_FLAVORS:
                continue
            raw_id = f.get("id") or f.get("str_id")
            if raw_id in (None, ""):
                continue
            result.append(
                {
                    "id": str(raw_id),
                    "name": name,
                    "ram": f.get("ram", 0) or 0,
                    "vcpus": f.get("vcpus", 0) or 0,
                    "disk": f.get("disk", 0) or 0,
                }
            )
        return result
    except Exception:
        _logger.debug("Trove 플레이버 목록 조회 실패", exc_info=True)
        return []


def list_datastores(conn) -> list[dict]:
    """데이터스토어 목록 (raw REST).

    name/version 이 빈 문자열이면 select value 가 비어 form validation 실패 →
    이름 없는 datastore/version 은 응답에서 제외.
    """
    try:
        resp = conn.database.get("/datastores")
        body = resp.json() if hasattr(resp, "json") else {}
        datastores_raw = body.get("datastores", [])
        result = []
        for ds in datastores_raw:
            ds_name = ds.get("name", "") or ""
            if not ds_name:
                continue
            versions = []
            for v in ds.get("versions", []):
                v_name = v.get("name", "") or v.get("version", "") or ""
                if not v_name:
                    continue
                versions.append({"id": str(v.get("id", "") or v_name), "name": v_name})
            result.append(
                {
                    "id": str(ds.get("id", "") or ds_name),
                    "name": ds_name,
                    "versions": versions,
                }
            )
        return result
    except Exception:
        _logger.debug("Trove 데이터스토어 목록 조회 실패", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# 백업 (SDK 미지원 → raw REST)
# ---------------------------------------------------------------------------


def _backup_to_dict(b: dict) -> dict:
    return {
        "id": b.get("id", ""),
        "name": b.get("name", ""),
        "description": b.get("description", ""),
        "status": b.get("status", ""),
        "instance_id": b.get("instance_id", ""),
        "size": b.get("size", 0),
        "created_at": b.get("created", "") or b.get("created_at", ""),
        "updated_at": b.get("updated", "") or b.get("updated_at", ""),
    }


def list_backups(conn, instance_id: str | None = None) -> list[dict]:
    """백업 목록. instance_id 지정 시 해당 인스턴스 백업만 반환."""
    try:
        url = f"/instances/{instance_id}/backups" if instance_id else "/backups"
        resp = conn.database.get(url)
        body = resp.json() if hasattr(resp, "json") else {}
        return [_backup_to_dict(b) for b in body.get("backups", [])]
    except Exception:
        _logger.debug("Trove 백업 목록 조회 실패", exc_info=True)
        return []


def create_backup(conn, instance_id: str, name: str, description: str = "") -> dict:
    """백업 생성."""
    payload: dict = {"backup": {"instance": instance_id, "name": name}}
    if description:
        payload["backup"]["description"] = description
    resp = conn.database.post("/backups", json=payload)
    body = resp.json() if hasattr(resp, "json") else {}
    return _backup_to_dict(body.get("backup", {}))


def delete_backup(conn, backup_id: str) -> None:
    """백업 삭제."""
    conn.database.delete(f"/backups/{backup_id}")


def get_backup(conn, backup_id: str) -> dict:
    """백업 상세 조회."""
    resp = conn.database.get(f"/backups/{backup_id}")
    body = resp.json() if hasattr(resp, "json") else {}
    return _backup_to_dict(body.get("backup", {}))


# ---------------------------------------------------------------------------
# 접근 제어 (is_public / allowed_cidrs)
# ---------------------------------------------------------------------------


def set_instance_access(conn, instance_id: str, is_public: bool, allowed_cidrs: list[str]) -> None:
    """인스턴스 접근 정책 설정 (is_public, allowed_cidrs)."""
    payload = {"access": {"is_public": is_public, "allowed_cidrs": allowed_cidrs}}
    conn.database.put(f"/instances/{instance_id}/access", json=payload)


# ---------------------------------------------------------------------------
# Configuration groups
# ---------------------------------------------------------------------------


def list_configurations(conn) -> list[dict]:
    """DB Configuration group 목록 (raw REST)."""
    try:
        resp = conn.database.get("/configurations")
        body = resp.json() if hasattr(resp, "json") else {}
        result = []
        for c in body.get("configurations", []):
            cfg_name = c.get("name", "") or ""
            cfg_id = str(c.get("id", "") or "")
            if not cfg_id:
                continue
            result.append(
                {
                    "id": cfg_id,
                    "name": cfg_name,
                    "datastore_name": c.get("datastore_name", "") or "",
                    "datastore_version_name": c.get("datastore_version_name", "") or "",
                }
            )
        return result
    except Exception:
        _logger.debug("Trove configuration group 목록 조회 실패", exc_info=True)
        return []
