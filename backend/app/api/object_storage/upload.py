"""Direct upload (S3 multipart) + quarantine bucket 흐름 엔드포인트."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_os_conn, get_token_info
from app.config import get_settings
from app.services import s3 as s3_svc
from app.services import swift as swift_svc

router = APIRouter(prefix="/api/object-storage", tags=["object-storage-upload"])
_logger = logging.getLogger(__name__)


class UploadInitReq(BaseModel):
    object_name: str
    content_type: str
    size: int  # bytes


class UploadCompleteReq(BaseModel):
    transaction_id: str
    parts: list[dict]  # [{"part_number": int, "etag": str}, ...]


class UploadAbortReq(BaseModel):
    transaction_id: str


def _tx_key(tx_id: str) -> str:
    return f"afterglow:upload-tx:{tx_id}"


async def _save_tx(tx_id: str, data: dict) -> None:
    from app.services.cache import _get_redis

    redis = await _get_redis()
    await redis.setex(_tx_key(tx_id), get_settings().upload_tx_ttl_sec, json.dumps(data))


async def _get_tx(tx_id: str) -> dict | None:
    from app.services.cache import _get_redis

    redis = await _get_redis()
    raw = await redis.get(_tx_key(tx_id))
    return json.loads(raw) if raw else None


async def _del_tx(tx_id: str) -> None:
    from app.services.cache import _get_redis

    redis = await _get_redis()
    await redis.delete(_tx_key(tx_id))


def _verify_owner(tx: dict, token_info: dict) -> None:
    if tx.get("user_id") != token_info["user_id"] or tx.get("project_id") != token_info["project_id"]:
        raise HTTPException(status_code=403, detail="트랜잭션 권한 없음")


async def _scan_object(bucket: str, key: str) -> bool:
    """보안 스캔 placeholder. ClamAV/VirusTotal 연동 위치."""
    return True


@router.post("/{container}/upload/init")
async def upload_init(
    container: str,
    req: UploadInitReq,
    conn=Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """S3 Multipart Upload 초기화.

    1. 컨테이너 소유권 검증
    2. quarantine 버킷 생성 + CORS 설정
    3. Multipart Upload 초기화
    4. 각 part의 presigned URL 생성
    5. 트랜잭션 상태를 Redis에 저장
    """
    try:
        await asyncio.to_thread(swift_svc.get_container_metadata, conn, container)
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없거나 권한 없음")

    quarantine_bucket = f"{container}-quarantine"
    part_count, part_size = s3_svc.calc_parts(req.size)
    tx_id = str(uuid.uuid4())

    def _do_init():
        client = s3_svc.get_user_s3_client(
            token_info["token"],
            token_info["user_id"],
            token_info["project_id"],
        )
        s3_svc.ensure_bucket(client, quarantine_bucket)
        upload_id = s3_svc.init_multipart(client, quarantine_bucket, req.object_name, req.content_type)
        urls = [
            {
                "part_number": i + 1,
                "url": s3_svc.presign_part(client, quarantine_bucket, req.object_name, upload_id, i + 1),
            }
            for i in range(part_count)
        ]
        return upload_id, urls

    try:
        upload_id, parts = await asyncio.to_thread(_do_init)
    except Exception as e:
        _logger.exception("upload/init 실패: container=%s object=%s", container, req.object_name)
        raise HTTPException(status_code=500, detail=f"업로드 초기화 실패: {e!s:.200}")

    await _save_tx(
        tx_id,
        {
            "user_id": token_info["user_id"],
            "project_id": token_info["project_id"],
            "target_bucket": container,
            "object_name": req.object_name,
            "quarantine_bucket": quarantine_bucket,
            "upload_id": upload_id,
            "size": req.size,
            "content_type": req.content_type,
            "part_count": part_count,
            "part_size": part_size,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    return {
        "transaction_id": tx_id,
        "quarantine_bucket": quarantine_bucket,
        "upload_id": upload_id,
        "parts": parts,
        "part_size": part_size,
    }


@router.post("/{container}/upload/complete")
async def upload_complete(
    container: str,
    req: UploadCompleteReq,
    token_info: dict = Depends(get_token_info),
):
    """S3 Multipart Upload 완료 처리.

    1. 트랜잭션 검증
    2. Multipart Upload complete
    3. 보안 스캔 (placeholder)
    4. quarantine → target 버킷 server-side copy
    5. quarantine 객체 삭제
    """
    tx = await _get_tx(req.transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="트랜잭션 만료 또는 없음")
    _verify_owner(tx, token_info)
    if tx["target_bucket"] != container:
        raise HTTPException(status_code=400, detail="컨테이너 불일치")

    def _do_complete():
        client = s3_svc.get_user_s3_client(
            token_info["token"],
            token_info["user_id"],
            token_info["project_id"],
        )
        s3_svc.complete_multipart(
            client,
            tx["quarantine_bucket"],
            tx["object_name"],
            tx["upload_id"],
            req.parts,
        )
        return client

    try:
        client = await asyncio.to_thread(_do_complete)
    except Exception as e:
        _logger.exception("upload/complete 실패: container=%s object=%s", container, tx.get("object_name"))
        raise HTTPException(status_code=500, detail=f"업로드 완료 처리 실패: {e!s:.200}")

    if not await _scan_object(tx["quarantine_bucket"], tx["object_name"]):
        await asyncio.to_thread(s3_svc.delete_object, client, tx["quarantine_bucket"], tx["object_name"])
        await _del_tx(req.transaction_id)
        raise HTTPException(status_code=400, detail="보안 스캔 실패")

    try:
        await asyncio.to_thread(
            s3_svc.copy_object,
            client,
            tx["quarantine_bucket"],
            tx["object_name"],
            tx["target_bucket"],
            tx["object_name"],
        )
        await asyncio.to_thread(s3_svc.delete_object, client, tx["quarantine_bucket"], tx["object_name"])
    except Exception as e:
        _logger.exception("quarantine→target copy 실패: %s → %s", tx["quarantine_bucket"], tx["target_bucket"])
        raise HTTPException(status_code=500, detail=f"파일 이동 실패: {e!s:.200}")

    await _del_tx(req.transaction_id)
    return {"success": True, "object_name": tx["object_name"], "bytes": tx["size"]}


@router.post("/{container}/upload/abort")
async def upload_abort(
    container: str,
    req: UploadAbortReq,
    token_info: dict = Depends(get_token_info),
):
    """S3 Multipart Upload 중단. 이미 abort/complete된 경우 무시."""
    tx = await _get_tx(req.transaction_id)
    if not tx:
        return {"success": True}
    _verify_owner(tx, token_info)

    def _do_abort():
        client = s3_svc.get_user_s3_client(
            token_info["token"],
            token_info["user_id"],
            token_info["project_id"],
        )
        s3_svc.abort_multipart(client, tx["quarantine_bucket"], tx["object_name"], tx["upload_id"])

    try:
        await asyncio.to_thread(_do_abort)
    except Exception:
        pass  # 이미 abort/complete된 경우 무시

    await _del_tx(req.transaction_id)
    return {"success": True}
