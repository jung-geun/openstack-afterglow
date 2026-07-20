"""빌트인 AI 채팅 첨부 업로드 API — 전용 object storage 버킷.

POST /api/v1/chat/attachments (multipart) → 전용 chat-attachments 버킷에 저장 후 참조 반환.
반환 참조(key/mime/name)를 completions 요청의 attachments 로 넘기면 vision content 로 전달된다.

⚠️ 현재는 image/* 만 허용(vision). 그 외 타입은 후속(pdf 등 modality 확장 시).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_token_info
from app.services.chat import attachments as att

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_BYTES = 8 * 1024 * 1024  # base64 인라인 폴백 상한과 일치


@router.post("/attachments", status_code=201)
async def upload_attachment(file: UploadFile = File(...), token_info: dict = Depends(get_token_info)):
    mime = file.content_type or "application/octet-stream"
    if not att.is_image(mime):
        raise HTTPException(status_code=400, detail="현재는 이미지 첨부만 지원합니다")
    name = (file.filename or "image").strip() or "image"

    size = getattr(file, "size", None)
    if size is not None and size > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="첨부는 8MB 이하여야 합니다")

    key = att.new_key(token_info["user_id"], name)
    try:
        await asyncio.to_thread(
            att.upload,
            token_info["token"],
            token_info["user_id"],
            token_info["project_id"],
            key,
            file.file,
            mime,
        )
    except Exception:
        logger.warning("채팅 첨부 업로드 실패 user=%s", token_info.get("user_id"), exc_info=True)
        raise HTTPException(status_code=502, detail="첨부 업로드에 실패했습니다") from None

    return {"key": key, "mime": mime, "name": name}
