"""Swift / Ceph RGW (Object Storage) 서비스 래퍼.

openstacksdk의 conn.object_store 프록시를 사용.
서비스가 없거나 오류 시 빈 목록/기본값을 반환하여 optional 서비스로 동작.

주의: Swift "컨테이너"는 오브젝트 스토리지 버킷을 의미.
Zun "컨테이너"와 혼동 방지를 위해 변수/응답 키에 object_storage_ 접두어 사용.
"""

import logging
from collections.abc import Iterator

from openstack.exceptions import ResourceNotFound

_logger = logging.getLogger(__name__)


def _is_account_not_found(exc: Exception) -> bool:
    """Ceph RGW에서 Swift 계정이 초기화되지 않은 경우 404를 반환하는지 확인."""
    return isinstance(exc, ResourceNotFound) or (hasattr(exc, "status_code") and getattr(exc, "status_code", 0) == 404)


def list_containers(conn) -> list[dict]:
    """현재 계정의 오브젝트 스토리지 컨테이너(버킷) 목록 반환."""
    try:
        project_id = getattr(conn, "_afterglow_project_id", "unknown")
        try:
            endpoint = conn.object_store.get_endpoint()
        except Exception:
            endpoint = "(resolve failed)"
        _logger.info("Swift list_containers: project_id=%s endpoint=%s", project_id, endpoint)

        result = [
            {
                "name": c.name or "",
                "count": getattr(c, "count", 0) or 0,
                "bytes": getattr(c, "bytes", 0) or 0,
            }
            for c in conn.object_store.containers()
        ]
        _logger.info("Swift 컨테이너 목록 조회: %d개", len(result))
        return result
    except Exception as exc:
        if _is_account_not_found(exc):
            _logger.info("Swift 계정 미초기화 (404) — 빈 목록 반환")
        else:
            _logger.warning("Swift 컨테이너 목록 조회 실패", exc_info=True)
        return []


def count_containers(conn) -> int:
    """현재 계정의 오브젝트 스토리지 컨테이너 수 반환."""
    try:
        return sum(1 for _ in conn.object_store.containers())
    except Exception as exc:
        if not _is_account_not_found(exc):
            _logger.debug("Swift 컨테이너 수 조회 실패", exc_info=True)
        return 0


def get_account_metadata(conn) -> dict:
    """현재 계정의 오브젝트 스토리지 사용량 메타데이터 반환.

    반환: {container_count, object_count, bytes_used}
    """
    try:
        meta = conn.object_store.get_account_metadata()
        result = {
            "container_count": int(getattr(meta, "account_container_count", 0) or 0),
            "object_count": int(getattr(meta, "account_object_count", 0) or 0),
            "bytes_used": int(getattr(meta, "account_bytes_used", 0) or 0),
        }
        _logger.info(
            "Swift 계정 메타데이터: containers=%d objects=%d bytes=%d",
            result["container_count"],
            result["object_count"],
            result["bytes_used"],
        )
        return result
    except Exception as exc:
        if _is_account_not_found(exc):
            _logger.info("Swift 계정 미초기화 (404) — 기본값 반환")
        else:
            _logger.warning("Swift 계정 메타데이터 조회 실패", exc_info=True)
        return {"container_count": 0, "object_count": 0, "bytes_used": 0}


# ---------------------------------------------------------------------------
# 컨테이너 CRUD
# ---------------------------------------------------------------------------


def create_container(conn, name: str) -> dict:
    """오브젝트 스토리지 컨테이너를 생성하고 메타데이터를 반환.

    Ceph RGW 환경에서 openstacksdk의 create_container가 404를 반환할 수 있으므로,
    raw PUT 요청으로 직접 생성을 시도한다.
    """
    try:
        c = conn.object_store.create_container(name=name)
        return {"name": c.name or name, "count": 0, "bytes": 0}
    except Exception as sdk_err:
        _logger.warning("SDK create_container 실패, raw PUT 시도", exc_info=True)
        # fallback: raw session PUT (Ceph RGW Swift API 호환)
        try:
            resp = conn.object_store.put(f"/{name}", headers={"Content-Length": "0"})
            sc = getattr(resp, "status_code", 0)
            if sc in (201, 202, 204):
                _logger.info("Swift 컨테이너 생성 raw PUT 응답: %d", sc)
                return {"name": name, "count": 0, "bytes": 0}
            _logger.error("Swift 컨테이너 raw PUT 실패: status=%d", sc)
        except Exception:
            _logger.warning("raw PUT 자체 실패", exc_info=True)
        raise sdk_err


def delete_container(conn, name: str) -> None:
    """오브젝트 스토리지 컨테이너를 삭제."""
    conn.object_store.delete_container(name, ignore_missing=False)


def get_container_metadata(conn, name: str) -> dict:
    """컨테이너 메타데이터(오브젝트 수, 바이트 등) 반환."""
    meta = conn.object_store.get_container_metadata(name)
    return {
        "name": meta.name or name,
        "count": getattr(meta, "object_count", 0) or 0,
        "bytes": getattr(meta, "bytes_used", 0) or 0,
        "read_acl": getattr(meta, "read_ACL", "") or "",
        "write_acl": getattr(meta, "write_ACL", "") or "",
    }


# ---------------------------------------------------------------------------
# 오브젝트 CRUD
# ---------------------------------------------------------------------------


def list_objects(conn, container: str, prefix: str = "") -> list[dict]:
    """컨테이너 내 오브젝트 목록 반환."""
    try:
        kwargs = {}
        if prefix:
            kwargs["prefix"] = prefix
        return [
            {
                "name": o.name or "",
                "bytes": getattr(o, "size", None) or getattr(o, "content_length", 0) or 0,
                "content_type": getattr(o, "content_type", "") or "",
                "last_modified": str(getattr(o, "last_modified_at", "") or ""),
                "etag": getattr(o, "etag", "") or "",
            }
            for o in conn.object_store.objects(container, **kwargs)
        ]
    except Exception:
        _logger.debug("Swift 오브젝트 목록 조회 실패 container=%s", container, exc_info=True)
        return []


def upload_object(conn, container: str, name: str, data: bytes, content_type: str = "") -> dict:
    """오브젝트를 업로드하고 메타데이터를 반환."""
    kwargs: dict = {"data": data}
    if content_type:
        kwargs["content_type"] = content_type
    obj = conn.object_store.create_object(container, name, **kwargs)
    return {
        "name": obj.name or name,
        "container": container,
        "bytes": len(data),
        "etag": getattr(obj, "etag", "") or "",
    }


def stream_object(conn, container: str, name: str) -> tuple[Iterator[bytes], str, int]:
    """오브젝트를 스트리밍으로 반환. (chunk_iterator, content_type, content_length)"""
    # 메타데이터 먼저 가져오기
    meta = conn.object_store.get_object_metadata(name, container=container)
    content_type = getattr(meta, "content_type", None) or "application/octet-stream"
    content_length = int(getattr(meta, "content_length", 0) or 0)
    chunks = conn.object_store.stream_object(name, container=container, chunk_size=65536)
    return chunks, content_type, content_length


def delete_object(conn, container: str, name: str) -> None:
    """오브젝트를 삭제."""
    conn.object_store.delete_object(name, ignore_missing=False, container=container)


def get_object_metadata(conn, container: str, name: str) -> dict:
    """오브젝트 상세 메타데이터 반환."""
    meta = conn.object_store.get_object_metadata(name, container=container)
    return {
        "name": meta.name or name,
        "container": container,
        "bytes": int(getattr(meta, "content_length", 0) or 0),
        "content_type": getattr(meta, "content_type", "") or "",
        "last_modified": str(getattr(meta, "last_modified_at", "") or ""),
        "etag": getattr(meta, "etag", "") or "",
        "content_encoding": getattr(meta, "content_encoding", "") or "",
        "content_disposition": getattr(meta, "content_disposition", "") or "",
        "delete_at": str(getattr(meta, "delete_at", "") or ""),
    }
