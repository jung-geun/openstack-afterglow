"""채팅 첨부(이미지/파일) — 전용 object storage 버킷 저장 + vision content URL 해석.

흐름:
- 업로드: 전용 `chat-attachments` 버킷(프로젝트 스코프, 없으면 자동 생성)에 저장. key 반환.
- vision 전달: presigned GET URL 기본, 생성/검증 실패 시 **base64 data-URI 인라인 폴백**
  (외부 LLM 이 RGW 에 도달 못 해도 확실히 동작). 백엔드가 내부에서 오브젝트를 읽는다.

⚠️ 보안: S3 client 는 호출자 Keystone 토큰의 EC2 credential 로 발급 → 프로젝트 스코프.
base64 는 크기 상한(_MAX_INLINE_BYTES)으로 제한. content_type 은 image/* 만 vision 으로 인라인.
"""

from __future__ import annotations

import base64
import logging
import uuid

from app.services import s3

logger = logging.getLogger(__name__)

CHAT_BUCKET = "chat-attachments"
_PRESIGN_TTL_SECONDS = 900  # 스트림 지연을 견디도록 넉넉히
_MAX_INLINE_BYTES = 8 * 1024 * 1024  # base64 인라인 상한(원본 바이트)
_ALLOWED_IMAGE_PREFIX = "image/"


def _client(token: str, user_id: str, project_id: str):
    return s3.get_user_s3_client(token, user_id, project_id)


def new_key(user_id: str, filename: str) -> str:
    """충돌 없는 object key. user_id 로 네임스페이스."""
    safe = (filename or "file").replace("/", "_").strip() or "file"
    return f"{user_id}/{uuid.uuid4().hex}/{safe}"


def upload(token: str, user_id: str, project_id: str, key: str, file_stream, content_type: str) -> None:
    """전용 버킷 보장 후 업로드(직접 target 버킷). 예외는 호출부로 전파."""
    client = _client(token, user_id, project_id)
    s3.ensure_bucket(client, CHAT_BUCKET)
    s3.stream_upload_to_quarantine(client, CHAT_BUCKET, key, file_stream, content_type)


def is_image(mime: str | None) -> bool:
    return bool(mime) and mime.startswith(_ALLOWED_IMAGE_PREFIX)


def _base64_data_url(client, key: str, mime: str) -> str | None:
    """오브젝트를 내부에서 읽어 base64 data-URI 로. 상한 초과/오류 시 None."""
    try:
        obj = client.get_object(Bucket=CHAT_BUCKET, Key=key)
        body = obj["Body"].read(_MAX_INLINE_BYTES + 1)
        if len(body) > _MAX_INLINE_BYTES:
            logger.warning("첨부가 base64 인라인 상한 초과 key=%s", key)
            return None
        b64 = base64.b64encode(body).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        logger.warning("첨부 base64 인라인 실패 key=%s", key, exc_info=True)
        return None


def resolve_image_url(token: str, user_id: str, project_id: str, key: str, mime: str) -> str | None:
    """vision content 용 URL. presigned GET 우선, 실패 시 base64 폴백. 둘 다 실패면 None.

    presigned 는 토큰 저렴하지만 RGW 외부 도달성이 필요 — 생성 실패 시 base64 로 확실히 대체.
    """
    client = _client(token, user_id, project_id)
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": CHAT_BUCKET, "Key": key},
            ExpiresIn=_PRESIGN_TTL_SECONDS,
        )
        if url:
            return url
    except Exception:
        logger.warning("presigned URL 생성 실패 — base64 폴백 key=%s", key, exc_info=True)
    return _base64_data_url(client, key, mime)
