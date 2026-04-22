"""Swift / Ceph RGW (Object Storage) 서비스 래퍼.

openstacksdk의 conn.object_store 프록시를 사용.
서비스가 없거나 오류 시 빈 목록/기본값을 반환하여 optional 서비스로 동작.

주의: Swift "컨테이너"는 오브젝트 스토리지 버킷을 의미.
Zun "컨테이너"와 혼동 방지를 위해 변수/응답 키에 object_storage_ 접두어 사용.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


def _get_swift_endpoint(conn) -> str | None:
    """config.toml swift_endpoint 오버라이드가 있으면 반환, 없으면 None."""
    from app.config import get_settings

    settings = get_settings()
    endpoint = getattr(settings, "os_swift_endpoint", "")
    if endpoint:
        return endpoint.rstrip("/")
    return None


def _is_account_not_found(exc: Exception) -> bool:
    """Ceph RGW에서 Swift 계정이 초기화되지 않은 경우 404를 반환하는지 확인."""
    from openstack.exceptions import ResourceNotFound

    return isinstance(exc, ResourceNotFound) or (hasattr(exc, "status_code") and getattr(exc, "status_code", 0) == 404)


def _apply_endpoint_override(conn) -> None:
    """swift_endpoint 오버라이드가 설정된 경우 openstacksdk object_store proxy에 적용."""
    override = _get_swift_endpoint(conn)
    if override:
        conn.object_store._endpoint_override = override
        _logger.debug("Swift endpoint override 적용: %s", override)


def list_containers(conn) -> list[dict]:
    """현재 계정의 오브젝트 스토리지 컨테이너(버킷) 목록 반환."""
    _apply_endpoint_override(conn)
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
    _apply_endpoint_override(conn)
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
    _apply_endpoint_override(conn)
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


def _ensure_account(conn) -> bool:
    """Ceph RGW Swift 계정이 없으면 POST로 초기화 시도. 성공 시 True."""
    try:
        resp = conn.object_store.post("/", headers={"Content-Length": "0"})
        sc = getattr(resp, "status_code", 0)
        if sc in (200, 201, 202, 204):
            _logger.info("Swift 계정 초기화 성공: status=%d", sc)
            return True
        _logger.warning("Swift 계정 초기화 응답: status=%d", sc)
    except Exception:
        _logger.debug("Swift 계정 POST 초기화 실패", exc_info=True)
    # PUT fallback
    try:
        resp = conn.object_store.put("/", headers={"Content-Length": "0"})
        sc = getattr(resp, "status_code", 0)
        if sc in (200, 201, 202, 204):
            _logger.info("Swift 계정 PUT 초기화 성공: status=%d", sc)
            return True
        _logger.warning("Swift 계정 PUT 초기화 응답: status=%d", sc)
    except Exception:
        _logger.debug("Swift 계정 PUT 초기화 실패", exc_info=True)
    return False


def create_container(conn, name: str) -> dict:
    """오브젝트 스토리지 컨테이너를 생성하고 메타데이터를 반환.

    Ceph RGW 환경에서 계정이 미초기화 상태이면 자동으로 계정을 초기화한 뒤
    컨테이너 생성을 재시도한다.
    """
    _apply_endpoint_override(conn)
    try:
        c = conn.object_store.create_container(name=name)
        return {"name": c.name or name, "count": 0, "bytes": 0}
    except Exception as sdk_err:
        if not _is_account_not_found(sdk_err):
            raise
        _logger.warning("SDK create_container 실패 (404), 계정 초기화 후 재시도")

        # 1차: 계정 초기화 시도
        _ensure_account(conn)

        # 2차: raw PUT으로 컨테이너 생성 재시도
        try:
            resp = conn.object_store.put(f"/{name}", headers={"Content-Length": "0"})
            sc = getattr(resp, "status_code", 0)
            if sc in (201, 202, 204):
                _logger.info("Swift 컨테이너 생성 성공 (계정 초기화 후): status=%d", sc)
                return {"name": name, "count": 0, "bytes": 0}
            _logger.error("Swift 컨테이너 raw PUT 실패: status=%d", sc)
        except Exception:
            _logger.warning("raw PUT 자체 실패", exc_info=True)

        # 3차: SDK 재시도 (계정 초기화 성공 시 작동할 수 있음)
        try:
            c = conn.object_store.create_container(name=name)
            _logger.info("Swift 컨테이너 SDK 재시도 성공")
            return {"name": c.name or name, "count": 0, "bytes": 0}
        except Exception:
            _logger.debug("SDK 재시도도 실패", exc_info=True)

        raise sdk_err


def delete_container(conn, name: str) -> None:
    """오브젝트 스토리지 컨테이너를 삭제."""
    _apply_endpoint_override(conn)
    conn.object_store.delete_container(name, ignore_missing=False)


def get_container_metadata(conn, name: str) -> dict:
    """컨테이너 메타데이터(오브젝트 수, 바이트 등) 반환."""
    _apply_endpoint_override(conn)
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
    _apply_endpoint_override(conn)
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


def upload_object(conn, container: str, name: str, data, content_type: str = "", content_length: int = 0) -> dict:
    """오브젝트를 업로드하고 메타데이터를 반환.

    data: bytes 또는 file-like object (read() 메서드 지원).
    대용량 파일의 경우 file-like object를 전달하면 스트리밍으로 업로드되어 메모리 사용을 줄인다.
    """
    from app.config import get_settings

    _apply_endpoint_override(conn)

    # 대용량 업로드를 위해 타임아웃을 임시로 늘림
    settings = get_settings()
    upload_timeout = settings.os_swift_upload_timeout
    proxy = conn.object_store
    original_timeout = getattr(proxy, "timeout", None)
    proxy.timeout = upload_timeout
    try:
        kwargs: dict = {"data": data}
        if content_type:
            kwargs["content_type"] = content_type
        if content_length:
            kwargs["content_length"] = content_length
        obj = conn.object_store.create_object(container, name, **kwargs)
        actual_bytes = content_length if content_length else (len(data) if isinstance(data, bytes) else 0)
        return {
            "name": obj.name or name,
            "container": container,
            "bytes": actual_bytes,
            "etag": getattr(obj, "etag", "") or "",
        }
    finally:
        proxy.timeout = original_timeout


def stream_object(conn, container: str, name: str) -> tuple[Iterator[bytes], str, int]:
    """오브젝트를 스트리밍으로 반환. (chunk_iterator, content_type, content_length)"""
    _apply_endpoint_override(conn)
    # 메타데이터 먼저 가져오기
    meta = conn.object_store.get_object_metadata(name, container=container)
    content_type = getattr(meta, "content_type", None) or "application/octet-stream"
    content_length = int(getattr(meta, "content_length", 0) or 0)
    chunks = conn.object_store.stream_object(name, container=container, chunk_size=65536)
    return chunks, content_type, content_length


def delete_object(conn, container: str, name: str) -> None:
    """오브젝트를 삭제."""
    _apply_endpoint_override(conn)
    conn.object_store.delete_object(name, ignore_missing=False, container=container)


def get_object_metadata(conn, container: str, name: str) -> dict:
    """오브젝트 상세 메타데이터 반환."""
    _apply_endpoint_override(conn)
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
