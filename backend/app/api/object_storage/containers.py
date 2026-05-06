from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio
import contextlib
import json
import logging
import queue as _queue_module
import secrets
import urllib.parse

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_os_conn, get_token_info
from app.models.storage import (
    BulkDeleteRequest,
    CopyObjectRequest,
    CreateContainerRequest,
    CreateDirectoryRequest,
    MoveObjectRequest,
    RenameObjectRequest,
)

router = APIRouter()
_logger = logging.getLogger(__name__)

_EOF = object()


class _QueueIO:
    """async producer → sync consumer bridge: read(n) blocks until queue has enough data."""

    def __init__(self, q: _queue_module.Queue[object]) -> None:
        self._q = q
        self._buf = bytearray()
        self._done = False

    def read(self, n: int = -1) -> bytes:
        while not self._done and (n < 0 or len(self._buf) < n):
            item = self._q.get()
            if item is _EOF:
                self._done = True
                break
            self._buf.extend(item)  # type: ignore[arg-type]
        if n < 0 or len(self._buf) <= n:
            data = bytes(self._buf)
            self._buf = bytearray()
        else:
            data = bytes(self._buf[:n])
            del self._buf[:n]
        return data


async def _drain_to_queue(stream, q: _queue_module.Queue[object]) -> None:
    try:
        async for chunk in stream:
            await asyncio.to_thread(q.put, chunk)
    finally:
        try:
            await asyncio.to_thread(q.put, _EOF)
        except BaseException:
            pass


def _sanitize_object_name(name: str) -> str:
    name = "".join(c for c in name if ord(c) >= 0x20 and ord(c) != 0x7F)
    name = name.strip("/").strip() or "unnamed"
    return name[:1024]


# ---------------------------------------------------------------------------
# 계정 메타데이터
# ---------------------------------------------------------------------------


@router.get("/account")
async def get_object_storage_account(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 계정의 Swift 오브젝트 스토리지 사용량 메타데이터."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_account_metadata, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 스토리지 계정 정보 조회 실패")


# ---------------------------------------------------------------------------
# 컨테이너 목록 / 생성
# ---------------------------------------------------------------------------


def _list_all_projects_containers(admin_token: str) -> list[dict]:
    """모든 프로젝트로 fan-out 해서 Swift 컨테이너 집계."""
    from app.services import keystone, swift

    projects = keystone.list_projects(admin_token)
    out: list[dict] = []
    for p in projects:
        pid = p.get("id")
        if not pid:
            continue
        try:
            sub_conn = keystone.get_admin_connection_for_project(pid)
            try:
                containers = swift.list_containers(sub_conn)
            finally:
                sub_conn.close()
            for c in containers:
                out.append({**c, "project_id": pid, "project_name": p.get("name", "")})
        except Exception:
            _logger.warning("프로젝트 %s 의 Swift 컨테이너 조회 실패", pid, exc_info=True)
    return out


@router.get("")
async def list_object_storage_containers(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
    all_projects: bool = Query(False, description="admin 전용: 모든 프로젝트 버킷"),
):
    """Swift 오브젝트 스토리지 컨테이너 목록. all_projects=true 는 시스템 admin 전용."""
    from app.services import swift

    if all_projects:
        if not token_info.get("is_system_admin", False):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
        try:
            return await asyncio.to_thread(_list_all_projects_containers, token_info["token"])
        except Exception:
            _logger.exception("관리자 Swift 버킷 전체 조회 실패")
            raise HTTPException(status_code=500, detail="오브젝트 스토리지 컨테이너 목록 조회 실패")

    try:
        return await asyncio.to_thread(swift.list_containers, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 스토리지 컨테이너 목록 조회 실패")


@router.post("", status_code=201)
async def create_object_storage_container(
    req: CreateContainerRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 스토리지 컨테이너(버킷) 생성."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.create_container, conn, req.name)
    except Exception:
        _logger.exception("Swift 컨테이너 생성 실패: name=%s", req.name)
        raise HTTPException(status_code=500, detail="컨테이너 생성 실패")


# ---------------------------------------------------------------------------
# 개별 컨테이너 — 상세 / 삭제
# ---------------------------------------------------------------------------


@router.get("/{container_name}")
async def get_object_storage_container(
    container_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """컨테이너 메타데이터(오브젝트 수, 바이트 등) 조회."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_container_metadata, conn, container_name)
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


@router.delete("/{container_name}", status_code=204)
async def delete_object_storage_container(
    container_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 스토리지 컨테이너 삭제 (비어있어야 함)."""
    from app.services import swift

    try:
        await asyncio.to_thread(swift.delete_container, conn, container_name)
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 삭제 실패")


# ---------------------------------------------------------------------------
# 오브젝트 목록 / 업로드
# ---------------------------------------------------------------------------


@router.get("/{container_name}/objects")
async def list_objects(
    container_name: str,
    prefix: str = Query(default=""),
    delimiter: str = Query(default="/"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """컨테이너 내 오브젝트 목록.

    delimiter="/"(기본값)를 사용하면 현재 prefix의 직속 파일과 서브디렉토리만 반환한다.
    delimiter=""로 요청하면 모든 오브젝트를 flat하게 반환한다.
    """
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.list_objects, conn, container_name, prefix, delimiter)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 목록 조회 실패")


@router.post("/{container_name}/objects", status_code=201)
async def upload_object(
    container_name: str,
    file: UploadFile,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 업로드 (multipart/form-data). 1 GiB 초과 시 Swift SLO 자동 적용."""
    from app.services import swift

    # 파일 크기 확인 (file.size가 없으면 seek으로 계산)
    if file.size is not None:
        file_size = file.size
    else:
        await file.seek(0, 2)
        file_size = await file.tell()
        await file.seek(0)

    try:
        object_name = _sanitize_object_name(file.filename or "unnamed")
        content_type = file.content_type or ""
        # file.file (SpooledTemporaryFile)을 직접 전달해 스트리밍 업로드
        return await asyncio.to_thread(
            swift.upload_object,
            conn,
            container_name,
            object_name,
            file.file,
            content_type,
            file_size,
        )
    except HTTPException:
        raise
    except Exception:
        _logger.exception("오브젝트 업로드 실패: container=%s name=%s", container_name, file.filename)
        raise HTTPException(status_code=500, detail="오브젝트 업로드 실패")


@router.put("/{container_name}/objects/{object_name:path}", status_code=201)
async def upload_object_stream(
    container_name: str,
    object_name: str,
    request: Request,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """streaming PUT — disk spool 없이 raw body 를 Swift 에 직접 forward.

    헤더: Content-Length (필수), Content-Type (선택).
    Content-Length > 1 GiB 이면 Swift SLO 자동 적용.
    """
    from app.services import swift

    cl = request.headers.get("content-length")
    if cl is None:
        raise HTTPException(status_code=411, detail="Content-Length 헤더 필수")
    try:
        file_size = int(cl)
    except ValueError:
        raise HTTPException(status_code=400, detail="Content-Length 값이 올바르지 않습니다")
    if file_size > 100 * 1024**3:
        raise HTTPException(status_code=413, detail="파일 크기는 100 GB를 초과할 수 없습니다")

    content_type = request.headers.get("content-type", "application/octet-stream")
    sanitized_name = _sanitize_object_name(object_name)

    _q: _queue_module.Queue[object] = _queue_module.Queue(maxsize=4)
    drain_task = asyncio.create_task(_drain_to_queue(request.stream(), _q))
    try:
        result = await asyncio.to_thread(
            swift.upload_object,
            conn,
            container_name,
            sanitized_name,
            _QueueIO(_q),
            content_type,
            file_size,
        )
    except HTTPException:
        raise
    except Exception as _exc:
        import openstack.exceptions as _oe

        if isinstance(_exc, _oe.HttpException):
            _detail = getattr(_exc, "details", None) or getattr(_exc, "message", None) or str(_exc)
            _sc = getattr(_exc, "status_code", None) or 500
            _sc = int(_sc) if isinstance(_sc, (int, str)) and str(_sc).isdigit() else 500
            _sc = _sc if 400 <= _sc < 600 else 500
            _logger.error(
                "스트리밍 업로드 swift 오류: container=%s name=%s status=%d detail=%s",
                container_name,
                sanitized_name,
                _sc,
                _detail,
            )
            raise HTTPException(status_code=_sc, detail=f"swift 오류: {_detail}")
        _logger.exception("스트리밍 업로드 실패: container=%s name=%s", container_name, sanitized_name)
        raise HTTPException(status_code=500, detail=f"오브젝트 업로드 실패: {type(_exc).__name__}: {_exc}")
    finally:
        drain_task.cancel()
        while not _q.empty():
            try:
                _q.get_nowait()
            except _queue_module.Empty:
                break
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task
    return result


# ---------------------------------------------------------------------------
# 개별 오브젝트 — 다운로드 / 삭제 / 메타데이터
# (오브젝트 이름에 '/' 포함 가능 → :path 타입 사용)
# ---------------------------------------------------------------------------


def _make_content_disposition(disposition: str, object_name: str) -> str:
    """RFC 5987 형식의 Content-Disposition 값 생성. 한글 파일명을 올바르게 처리."""
    raw_name = object_name.split("/")[-1]
    quoted = urllib.parse.quote(raw_name, safe="")
    ascii_fallback = raw_name.encode("ascii", "replace").decode("ascii").replace("?", "_")
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"


async def _resolve_swift_conn(
    dl_token: str | None,
    container_name: str,
    object_name: str,
    x_auth_token: str | None,
    x_project_id: str | None,
) -> openstack.connection.Connection:
    """단발 다운로드 토큰 또는 헤더 인증으로 OpenStack 연결을 반환."""
    from app.services import keystone as ks
    from app.services.cache import _get_redis

    if dl_token:
        r = await _get_redis()
        payload_str = await r.getdel(f"dl-token:{dl_token}")
        if payload_str is None:
            raise HTTPException(status_code=403, detail="유효하지 않거나 만료된 다운로드 토큰입니다")
        payload = json.loads(payload_str)
        if payload["container_name"] != container_name or payload["object_name"] != object_name:
            raise HTTPException(status_code=403, detail="토큰이 요청한 리소스와 일치하지 않습니다")
        return await asyncio.to_thread(ks.get_openstack_connection, payload["openstack_token"], payload["project_id"])

    if not x_auth_token:
        raise HTTPException(status_code=401, detail="X-Auth-Token 헤더가 필요합니다")
    try:
        import hashlib

        from app.api.deps import _cached_validate, _check_session_timeout

        token_hash = hashlib.sha256(x_auth_token.encode()).hexdigest()
        await _check_session_timeout(token_hash, x_project_id or "")
        token_info = await _cached_validate(x_auth_token, x_project_id or "")
        return await asyncio.to_thread(ks.get_openstack_connection, token_info["token"], token_info["project_id"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")


@router.post("/{container_name}/objects/{object_name:path}/download-token", status_code=200)
async def issue_download_token(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """단발 다운로드 토큰 발급 (TTL 60초, 1회 사용). 브라우저 네이티브 다운로더 지원."""
    from app.services.cache import _get_redis

    token = secrets.token_urlsafe(32)
    payload = json.dumps(
        {
            "openstack_token": conn._afterglow_token,
            "project_id": conn._afterglow_project_id,
            "container_name": container_name,
            "object_name": object_name,
        }
    )
    r = await _get_redis()
    await r.set(f"dl-token:{token}", payload, ex=60)

    encoded_container = urllib.parse.quote(container_name, safe="")
    encoded_object = "/".join(urllib.parse.quote(p, safe="") for p in object_name.split("/"))
    url = f"/api/object-storage/{encoded_container}/objects/{encoded_object}/download?token={token}"
    return {"url": url, "expires_in": 60}


@router.get("/{container_name}/objects/{object_name:path}/download")
async def download_object(
    container_name: str,
    object_name: str,
    dl_token: str | None = Query(None, alias="token"),
    x_auth_token: str | None = Header(None),
    x_project_id: str | None = Header(None),
):
    """오브젝트 스트리밍 다운로드. 단발 토큰(?token=) 또는 X-Auth-Token 헤더 인증."""
    from app.services import swift

    conn = await _resolve_swift_conn(dl_token, container_name, object_name, x_auth_token, x_project_id)
    try:
        chunks, content_type, content_length = await asyncio.to_thread(
            swift.stream_object, conn, container_name, object_name
        )
        headers: dict[str, str] = {
            "Content-Disposition": _make_content_disposition("attachment", object_name),
        }
        if content_length:
            headers["Content-Length"] = str(content_length)

        sentinel = object()

        def _next_chunk():
            return next(chunks, sentinel)

        async def _iter():
            while True:
                chunk = await asyncio.to_thread(_next_chunk)
                if chunk is sentinel:
                    break
                yield chunk

        return StreamingResponse(_iter(), media_type=content_type, headers=headers)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="오브젝트를 찾을 수 없습니다")
    finally:
        await asyncio.to_thread(conn.close)


@router.delete("/{container_name}/objects/{object_name:path}", status_code=204)
async def delete_object(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 삭제."""
    from app.services import swift

    try:
        await asyncio.to_thread(swift.delete_object, conn, container_name, object_name)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 삭제 실패")


@router.get("/{container_name}/objects/{object_name:path}/metadata")
async def get_object_metadata(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 상세 메타데이터."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_object_metadata, conn, container_name, object_name)
    except Exception:
        raise HTTPException(status_code=404, detail="오브젝트를 찾을 수 없습니다")


@router.get("/{container_name}/objects/{object_name:path}/preview")
async def preview_object(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 인라인 미리보기 (Content-Disposition: inline)."""
    from app.services import swift

    try:
        chunks, content_type, content_length = await asyncio.to_thread(
            swift.stream_object, conn, container_name, object_name
        )
        headers: dict[str, str] = {
            "Content-Disposition": _make_content_disposition("inline", object_name),
        }
        if content_length:
            headers["Content-Length"] = str(content_length)

        sentinel = object()

        def _next_chunk():
            return next(chunks, sentinel)

        async def _iter():
            while True:
                chunk = await asyncio.to_thread(_next_chunk)
                if chunk is sentinel:
                    break
                yield chunk

        return StreamingResponse(_iter(), media_type=content_type, headers=headers)
    except Exception:
        raise HTTPException(status_code=404, detail="오브젝트를 찾을 수 없습니다")


# ---------------------------------------------------------------------------
# 일괄 삭제
# ---------------------------------------------------------------------------


@router.post("/{container_name}/objects/bulk-delete", status_code=200)
async def bulk_delete_objects(
    container_name: str,
    body: BulkDeleteRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 일괄 삭제.

    recursive=True이면 디렉토리(`/`로 끝나는) 하위 전체를 삭제한다.
    반환: {"deleted": [...], "failed": [{"name": ..., "error": ...}]}
    """
    from app.services import swift

    try:
        result = await asyncio.to_thread(swift.bulk_delete_objects, conn, container_name, body.objects, body.recursive)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="일괄 삭제 실패")


# ---------------------------------------------------------------------------
# 디렉토리 / 복사 / 이동 / 이름 변경
# ---------------------------------------------------------------------------


@router.post("/{container_name}/objects/directory", status_code=201)
async def create_directory(
    container_name: str,
    body: CreateDirectoryRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """가상 디렉토리 생성."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.create_directory, conn, container_name, body.path)
    except Exception:
        _logger.exception("디렉토리 생성 실패: container=%s path=%s", container_name, body.path)
        raise HTTPException(status_code=500, detail="디렉토리 생성 실패")


@router.post("/{container_name}/objects/copy", status_code=200)
async def copy_object(
    container_name: str,
    body: CopyObjectRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 복사."""
    from app.services import swift

    dest_container = body.dest_container or container_name
    try:
        return await asyncio.to_thread(
            swift.copy_object, conn, container_name, body.source, dest_container, body.destination
        )
    except Exception:
        _logger.exception("오브젝트 복사 실패: %s -> %s", body.source, body.destination)
        raise HTTPException(status_code=500, detail="오브젝트 복사 실패")


@router.post("/{container_name}/objects/move", status_code=200)
async def move_object(
    container_name: str,
    body: MoveObjectRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 이동.

    destination이 "/"로 끝나는 디렉토리 경로인 경우 원본 파일명을 자동으로 추가한다.
    예: source="a/b.txt", destination="folder/" → dest_name="folder/b.txt"
    """
    from app.services import swift

    dest_container = body.dest_container or container_name
    dest_name = body.destination
    # 디렉토리 경로로 이동할 경우 원본 파일명 유지
    if dest_name.endswith("/"):
        original_filename = body.source.rsplit("/", 1)[-1]
        dest_name = dest_name + original_filename
    try:
        return await asyncio.to_thread(swift.move_object, conn, container_name, body.source, dest_container, dest_name)
    except Exception:
        _logger.exception("오브젝트 이동 실패: %s -> %s", body.source, body.destination)
        raise HTTPException(status_code=500, detail="오브젝트 이동 실패")


@router.post("/{container_name}/objects/rename", status_code=200)
async def rename_object(
    container_name: str,
    body: RenameObjectRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 이름 변경."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.rename_object, conn, container_name, body.source, body.new_name)
    except Exception:
        _logger.exception("오브젝트 이름 변경 실패: %s -> %s", body.source, body.new_name)
        raise HTTPException(status_code=500, detail="오브젝트 이름 변경 실패")
