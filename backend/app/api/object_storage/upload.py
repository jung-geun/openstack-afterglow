"""백엔드 프록시 업로드 흐름 (Phase 9).

흐름:
  1. multipart/form-data 로 파일 수신 (FastAPI UploadFile)
  2. 컨테이너 소유권 검증 (swift.get_container_metadata)
  3. quarantine 버킷 ensure (boto3 ensure_bucket)
  4. boto3 streaming upload (upload_fileobj + TransferConfig, 5GB+ 자동 multipart)
  5. 보안 스캔 placeholder (_scan_object — Phase 10 에서 ClamAV 등 연동)
  6. server-side copy → target 버킷, quarantine 원본 삭제
  7. 메타데이터 반환

브라우저 → RGW 직접 PUT 의 CORS 차단 문제를 회피.

취소(cancel): 클라가 connection 을 끊으면 disconnect watcher 가 cancel_event 를
set → boto3 Callback 이 다음 part 시점에 UploadCanceled raise → multipart 자동
abort → quarantine 정리. copy 단계까지 진입한 경우는 server-side 라 짧으므로
중단하지 않음.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.deps import get_os_conn, get_token_info
from app.api.object_storage.containers import _sanitize_object_name
from app.config import get_settings
from app.services import s3 as s3_svc
from app.services import swift as swift_svc

router = APIRouter(prefix="/api/object-storage", tags=["object-storage-upload"])
_logger = logging.getLogger(__name__)


def _scan_object(client, bucket: str, key: str) -> bool:
    """보안 스캔 placeholder. ClamAV/VirusTotal 등 동기 호출 위치 (Phase 10)."""
    return True


@router.post("/{container}/upload")
async def upload_object(
    container: str,
    request: Request,
    file: UploadFile = File(...),
    prefix: str = Form(""),
    conn=Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """백엔드 프록시 업로드: 클라 → backend (form) → quarantine S3 → 검증 → target S3.

    - 5GB+ 자동 multipart (boto3 upload_fileobj + TransferConfig)
    - 검증 실패 시 quarantine 객체 정리, 400
    - 클라 disconnect 시 boto3 Callback 으로 UploadCanceled raise → multipart abort
    - 모든 예외 시 quarantine 정리 보장
    """
    _logger.warning(
        "[upload-entry] container=%s prefix=%r filename=%r content_type=%r size=%r",
        container,
        prefix,
        file.filename,
        file.content_type,
        getattr(file, "size", None),
    )

    try:
        await asyncio.to_thread(swift_svc.get_container_metadata, conn, container)
    except Exception:
        _logger.warning("컨테이너 검증 실패: container=%s", container, exc_info=True)
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없거나 권한 없음")

    quarantine_bucket = f"{container}-quarantine"
    raw_name = (prefix or "") + (file.filename or "")
    object_name = _sanitize_object_name(raw_name)
    # sanitize 후 의미 있는 이름이 남았는지 — `unnamed` fallback 은 명시적 거부
    if not (file.filename or "").strip() or object_name == "unnamed":
        _logger.warning("파일 이름 없음/유효치 않음: prefix=%r filename=%r", prefix, file.filename)
        raise HTTPException(status_code=400, detail="파일 이름이 비어 있거나 유효하지 않습니다")

    # 업로드 크기 cap — settings.app_max_upload_gb (기본 10GB). 클라가 헤더 위장해도
    # boto3 streaming 단계에서 추가 검증되지만 빠른 거부를 위해 사전 체크.
    settings = get_settings()
    max_bytes = settings.app_max_upload_gb * 1024**3
    incoming_size = getattr(file, "size", None)
    if incoming_size is not None and incoming_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"업로드 파일이 최대 허용 크기({settings.app_max_upload_gb}GB)를 초과합니다",
        )

    content_type = file.content_type or "application/octet-stream"

    cancel_event = threading.Event()

    async def _watch_disconnect() -> None:
        """request.receive() 에 block → http.disconnect 도달 시 cancel_event 활성화.

        starlette 의 request.is_disconnected() 는 timeout=0 polling 이라 신뢰성
        낮음. FastAPI 가 UploadFile 파라미터를 처리하며 body 를 모두 소비한 후
        receive() 는 http.disconnect 만 큐에 들어옴 → block + 즉시 감지.
        """
        try:
            while not cancel_event.is_set():
                message = await request.receive()
                if message.get("type") == "http.disconnect":
                    cancel_event.set()
                    _logger.info(
                        "upload cancel: client disconnected (container=%s name=%s)",
                        container,
                        object_name,
                    )
                    return
        except asyncio.CancelledError:
            pass
        except Exception:
            _logger.warning("disconnect watcher 오류", exc_info=True)

    def _do_pipeline() -> dict:
        client = s3_svc.get_user_s3_client(
            token_info["token"],
            token_info["user_id"],
            token_info["project_id"],
        )
        s3_svc.ensure_bucket(client, quarantine_bucket)
        try:
            s3_svc.stream_upload_to_quarantine(
                client,
                quarantine_bucket,
                object_name,
                file.file,
                content_type,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set():
                raise s3_svc.UploadCanceled("client disconnected")
            if not _scan_object(client, quarantine_bucket, object_name):
                raise HTTPException(status_code=400, detail="보안 스캔 실패")
            return s3_svc.move_to_target(client, quarantine_bucket, container, object_name)
        except BaseException:
            # 모든 종료 경로에서 quarantine 정리 (성공 시는 move_to_target 가 이미 삭제)
            _safe_delete_quarantine(client, quarantine_bucket, object_name)
            raise

    watch_task = asyncio.create_task(_watch_disconnect())
    try:
        meta = await asyncio.to_thread(_do_pipeline)
    except s3_svc.UploadCanceled:
        _logger.info("upload aborted: container=%s name=%s", container, object_name)
        # 499 = "Client Closed Request" (nginx 관행). 클라는 이미 connection
        # 닫혔으므로 응답은 도달하지 않음. 로그/메트릭 분류용.
        raise HTTPException(status_code=499, detail="업로드가 취소되었습니다")
    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("upload 실패: container=%s name=%s", container, object_name)
        raise HTTPException(status_code=500, detail=f"업로드 실패: {e!s:.200}")
    finally:
        cancel_event.set()
        watch_task.cancel()

    return {"success": True, **meta}


def _safe_delete_quarantine(client, bucket: str, key: str) -> None:
    """quarantine 객체 best-effort 삭제. 예외는 swallow."""
    try:
        s3_svc.delete_object(client, bucket, key)
    except Exception:
        _logger.warning("quarantine 정리 실패: %s/%s", bucket, key, exc_info=True)
