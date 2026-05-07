"""boto3 기반 S3 wrapper. Ceph RGW S3 endpoint 대상.

백엔드 프록시 업로드 흐름 (Phase 9):
  client → backend (form) → quarantine bucket → 검증 → target bucket (server-side copy)
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def get_user_s3_client(token: str, user_id: str, project_id: str):
    """Keystone EC2 credentials → boto3 S3 client (SigV4, path addressing)."""
    import boto3
    import boto3.session

    from app.config import get_settings
    from app.services.keystone import ensure_ec2_credentials

    creds = ensure_ec2_credentials(token, user_id, project_id)
    settings = get_settings()
    # boto3 1.36+ 기본 동작은 모든 요청에 CRC32 등 추가 checksum 을 계산하는데,
    # Ceph RGW 가 이 헤더를 SHA256 hash 로 오해해 XAmzContentSHA256Mismatch 로
    # multipart upload_part 가 실패한다. when_required 로 명시해 회피.
    return boto3.client(
        "s3",
        endpoint_url=settings.os_s3_endpoint,
        aws_access_key_id=creds["access"],
        aws_secret_access_key=creds["secret"],
        region_name="default",
        config=boto3.session.Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def ensure_bucket(client, bucket: str) -> None:
    """버킷이 없으면 생성. 있든 없든 CORS 는 항상 최신 cors_origins 로 재적용 (idempotent)."""
    from botocore.exceptions import ClientError

    try:
        client.head_bucket(Bucket=bucket)
        exists = True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchBucket", "NotFound"):
            client.create_bucket(Bucket=bucket)
            _logger.info("quarantine 버킷 생성: %s", bucket)
            exists = False
        else:
            raise

    try:
        _put_bucket_cors(client, bucket)
        _logger.debug("quarantine 버킷 CORS 갱신: %s (existing=%s)", bucket, exists)
    except Exception:
        _logger.warning("quarantine 버킷 CORS 갱신 실패: %s", bucket, exc_info=True)


def _put_bucket_cors(client, bucket: str) -> None:
    """RGW bucket CORS 설정. Phase 9 흐름에서는 사실상 불필요하나 idempotent 유지."""
    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": ["*"],
                    "AllowedMethods": ["PUT", "POST", "GET", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )


class UploadCanceled(Exception):
    """클라이언트 disconnect 등으로 업로드가 취소되었을 때 raise."""


def stream_upload_to_quarantine(
    client,
    quarantine_bucket: str,
    key: str,
    file_stream,
    content_type: str,
    cancel_event=None,
) -> None:
    """boto3 upload_fileobj + TransferConfig 로 quarantine 버킷에 streaming upload.

    multipart_threshold=8MB, multipart_chunksize=8MB, max_concurrency=4.
    5 GB 이상은 자동 multipart upload, 5 TiB 까지 단일 호출로 처리.
    file_stream 은 SpooledTemporaryFile 등 read/seek 지원 객체여야 한다.

    cancel_event (threading.Event) 가 set 되면 다음 part 진행 시점에
    UploadCanceled 를 raise → boto3 가 multipart 자동 abort.
    """
    from boto3.s3.transfer import TransferConfig

    config = TransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        multipart_chunksize=8 * 1024 * 1024,
        max_concurrency=4,
        use_threads=True,
    )

    def _progress(_bytes_amount: int) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise UploadCanceled("client disconnected")

    client.upload_fileobj(
        Fileobj=file_stream,
        Bucket=quarantine_bucket,
        Key=key,
        ExtraArgs={"ContentType": content_type},
        Config=config,
        Callback=_progress,
    )


def copy_object(client, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> None:
    """S3 server-side copy. boto3 client.copy() 가 5 GiB 초과 시 자동 multipart copy."""
    client.copy(
        CopySource={"Bucket": src_bucket, "Key": src_key},
        Bucket=dst_bucket,
        Key=dst_key,
    )


def delete_object(client, bucket: str, key: str) -> None:
    """S3 객체 삭제."""
    client.delete_object(Bucket=bucket, Key=key)


def move_to_target(
    client,
    quarantine_bucket: str,
    target_bucket: str,
    key: str,
) -> dict:
    """quarantine → target server-side copy + quarantine 원본 삭제. metadata 반환."""
    copy_object(client, quarantine_bucket, key, target_bucket, key)
    head = client.head_object(Bucket=target_bucket, Key=key)
    delete_object(client, quarantine_bucket, key)
    return {
        "name": key,
        "bytes": head.get("ContentLength", 0),
        "etag": (head.get("ETag", "") or "").strip('"'),
        "content_type": head.get("ContentType", ""),
    }
