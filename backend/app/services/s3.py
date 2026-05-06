"""boto3 기반 S3 wrapper. Ceph RGW S3 endpoint 대상."""

from __future__ import annotations

import logging
import math

_logger = logging.getLogger(__name__)

PART_SIZE_MIN = 5 * 1024 * 1024  # 5 MiB (S3 spec, 마지막 part 제외)
PART_COUNT_MAX = 1000


def calc_parts(size: int) -> tuple[int, int]:
    """파일 크기 → (part_count, part_size).

    Returns:
        (part_count, part_size_bytes)
    """
    from app.config import get_settings

    target = get_settings().upload_part_size_mb * 1024 * 1024
    if size <= target:
        return 1, max(size, 1)
    part_count = min(PART_COUNT_MAX, max(1, math.ceil(size / target)))
    part_size = max(PART_SIZE_MIN, math.ceil(size / part_count))
    actual_count = math.ceil(size / part_size)
    return actual_count, part_size


def get_user_s3_client(token: str, user_id: str, project_id: str):
    """Keystone EC2 credentials → boto3 S3 client (SigV4, path addressing)."""
    import boto3
    import boto3.session

    from app.config import get_settings
    from app.services.keystone import ensure_ec2_credentials

    creds = ensure_ec2_credentials(token, user_id, project_id)
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.os_s3_endpoint,
        aws_access_key_id=creds["access"],
        aws_secret_access_key=creds["secret"],
        region_name="default",
        config=boto3.session.Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def ensure_bucket(client, bucket: str) -> None:
    """버킷이 없으면 생성하고 CORS를 설정."""
    from botocore.exceptions import ClientError

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchBucket", "NotFound"):
            client.create_bucket(Bucket=bucket)
            _put_bucket_cors(client, bucket)
            _logger.info("quarantine 버킷 생성 + CORS 설정: %s", bucket)
        else:
            raise


def _put_bucket_cors(client, bucket: str) -> None:
    """RGW bucket에 CORS 설정 — 브라우저 직접 PUT 허용."""
    from app.config import get_settings

    origin = get_settings().app_origin
    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": [origin],
                    "AllowedMethods": ["PUT", "POST", "GET", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )


def init_multipart(client, bucket: str, key: str, content_type: str) -> str:
    """S3 Multipart Upload 초기화. upload_id 반환."""
    resp = client.create_multipart_upload(Bucket=bucket, Key=key, ContentType=content_type)
    return resp["UploadId"]


def presign_part(client, bucket: str, key: str, upload_id: str, part_number: int) -> str:
    """part 업로드용 presigned PUT URL 생성."""
    from app.config import get_settings

    return client.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": bucket,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=get_settings().upload_url_expires_sec,
        HttpMethod="PUT",
    )


def complete_multipart(client, bucket: str, key: str, upload_id: str, parts: list[dict]) -> str:
    """S3 Multipart Upload 완료. parts = [{"part_number": int, "etag": str}, ...]. ETag 반환."""
    resp = client.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={
            "Parts": [
                {"PartNumber": p["part_number"], "ETag": p["etag"]}
                for p in sorted(parts, key=lambda x: x["part_number"])
            ]
        },
    )
    return resp.get("ETag", "")


def abort_multipart(client, bucket: str, key: str, upload_id: str) -> None:
    """S3 Multipart Upload 중단."""
    client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)


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
