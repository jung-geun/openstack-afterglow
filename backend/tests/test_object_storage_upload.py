"""백엔드 프록시 업로드 (Phase 9) 테스트.

흐름: client → backend (form) → quarantine S3 → 검증 → target S3 → metadata 응답
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# stream_upload_to_quarantine / move_to_target 단위 테스트
# ---------------------------------------------------------------------------


def test_stream_upload_uses_transfer_config():
    """stream_upload_to_quarantine 가 TransferConfig 와 ContentType 를 전달한다."""
    from app.services import s3 as s3_svc

    fake = MagicMock()
    stream = MagicMock()
    s3_svc.stream_upload_to_quarantine(fake, "test-quarantine", "obj.bin", stream, "application/zip")

    fake.upload_fileobj.assert_called_once()
    kwargs = fake.upload_fileobj.call_args.kwargs
    assert kwargs["Bucket"] == "test-quarantine"
    assert kwargs["Key"] == "obj.bin"
    assert kwargs["Fileobj"] is stream
    assert kwargs["ExtraArgs"] == {"ContentType": "application/zip"}
    assert kwargs["Config"] is not None
    cfg = kwargs["Config"]
    assert cfg.multipart_threshold == 8 * 1024 * 1024
    assert cfg.multipart_chunksize == 8 * 1024 * 1024
    assert cfg.max_concurrency == 4


def test_move_to_target_copies_then_deletes_quarantine():
    """move_to_target: copy → head → delete quarantine. metadata 반환."""
    from app.services import s3 as s3_svc

    fake = MagicMock()
    fake.head_object.return_value = {
        "ContentLength": 1234,
        "ETag": '"abc123"',
        "ContentType": "application/pdf",
    }

    meta = s3_svc.move_to_target(fake, "test-quarantine", "test", "report.pdf")

    fake.copy.assert_called_once_with(
        CopySource={"Bucket": "test-quarantine", "Key": "report.pdf"},
        Bucket="test",
        Key="report.pdf",
    )
    fake.head_object.assert_called_once_with(Bucket="test", Key="report.pdf")
    fake.delete_object.assert_called_once_with(Bucket="test-quarantine", Key="report.pdf")
    assert meta == {
        "name": "report.pdf",
        "bytes": 1234,
        "etag": "abc123",
        "content_type": "application/pdf",
    }


# ---------------------------------------------------------------------------
# POST /upload 엔드포인트 통합 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_normal_flow(client, mock_conn, monkeypatch):
    """정상 흐름: ensure_bucket → stream_upload → scan(True) → move_to_target → 200."""
    fake_s3 = MagicMock()
    fake_s3.head_object.return_value = {
        "ContentLength": 7,
        "ETag": '"deadbeef"',
        "ContentType": "text/plain",
    }

    monkeypatch.setattr(
        "app.api.object_storage.upload.s3_svc.get_user_s3_client",
        lambda *a, **kw: fake_s3,
    )
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        lambda *a, **kw: {"name": "test"},
    )

    resp = await client.post(
        "/api/object-storage/test/upload",
        files={"file": ("hello.txt", b"hello!\n", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["name"] == "hello.txt"
    assert body["bytes"] == 7
    assert body["etag"] == "deadbeef"
    fake_s3.upload_fileobj.assert_called_once()
    fake_s3.copy.assert_called_once()
    # quarantine 정상 정리: move_to_target 내부 delete_object 1회
    assert fake_s3.delete_object.call_count == 1
    fake_s3.delete_object.assert_called_with(Bucket="test-quarantine", Key="hello.txt")


@pytest.mark.asyncio
async def test_upload_rejects_nonexistent_container(client, mock_conn, monkeypatch):
    """컨테이너 소유권 검증 실패 → 404."""
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        MagicMock(side_effect=Exception("not found")),
    )

    resp = await client.post(
        "/api/object-storage/other-bucket/upload",
        files={"file": ("x.bin", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_scan_failure_cleans_quarantine(client, mock_conn, monkeypatch):
    """검증 실패 → quarantine 객체 삭제 + 400."""
    fake_s3 = MagicMock()

    monkeypatch.setattr(
        "app.api.object_storage.upload.s3_svc.get_user_s3_client",
        lambda *a, **kw: fake_s3,
    )
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        lambda *a, **kw: {"name": "test"},
    )
    monkeypatch.setattr(
        "app.api.object_storage.upload._scan_object",
        lambda *a, **kw: False,
    )

    resp = await client.post(
        "/api/object-storage/test/upload",
        files={"file": ("malicious.bin", b"bad", "application/octet-stream")},
    )
    assert resp.status_code == 400
    fake_s3.upload_fileobj.assert_called_once()
    # copy 미호출
    fake_s3.copy.assert_not_called()
    # quarantine 객체 삭제
    fake_s3.delete_object.assert_called_once_with(Bucket="test-quarantine", Key="malicious.bin")


@pytest.mark.asyncio
async def test_upload_stream_exception_cleans_quarantine(client, mock_conn, monkeypatch):
    """stream_upload 도중 예외 → quarantine best-effort 정리 + 500."""
    fake_s3 = MagicMock()
    fake_s3.upload_fileobj.side_effect = RuntimeError("RGW 네트워크 오류")

    monkeypatch.setattr(
        "app.api.object_storage.upload.s3_svc.get_user_s3_client",
        lambda *a, **kw: fake_s3,
    )
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        lambda *a, **kw: {"name": "test"},
    )

    resp = await client.post(
        "/api/object-storage/test/upload",
        files={"file": ("crash.bin", b"data", "application/octet-stream")},
    )
    assert resp.status_code == 500
    # quarantine 정리 시도
    fake_s3.delete_object.assert_called_once_with(Bucket="test-quarantine", Key="crash.bin")


@pytest.mark.asyncio
async def test_upload_with_prefix(client, mock_conn, monkeypatch):
    """prefix 가 object_name 에 포함된다."""
    fake_s3 = MagicMock()
    fake_s3.head_object.return_value = {
        "ContentLength": 1,
        "ETag": '"e"',
        "ContentType": "text/plain",
    }

    monkeypatch.setattr(
        "app.api.object_storage.upload.s3_svc.get_user_s3_client",
        lambda *a, **kw: fake_s3,
    )
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        lambda *a, **kw: {"name": "test"},
    )

    resp = await client.post(
        "/api/object-storage/test/upload",
        files={"file": ("notes.md", b"x", "text/markdown")},
        data={"prefix": "docs/"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "docs/notes.md"
    upload_kwargs = fake_s3.upload_fileobj.call_args.kwargs
    assert upload_kwargs["Key"] == "docs/notes.md"


# ---------------------------------------------------------------------------
# CORS 적용 회귀 (ensure_bucket idempotent)
# ---------------------------------------------------------------------------


def test_put_bucket_cors_uses_wildcard_origin():
    """_put_bucket_cors 가 AllowedOrigins=["*"] 를 사용 (legacy)."""
    from app.services import s3 as s3_svc

    fake = MagicMock()
    s3_svc._put_bucket_cors(fake, "test-quarantine")

    fake.put_bucket_cors.assert_called_once()
    cfg = fake.put_bucket_cors.call_args.kwargs["CORSConfiguration"]
    rule = cfg["CORSRules"][0]
    assert rule["AllowedOrigins"] == ["*"]
    assert rule["MaxAgeSeconds"] == 3600
    assert "PUT" in rule["AllowedMethods"]
    assert "ETag" in rule["ExposeHeaders"]


def test_ensure_bucket_existing_reapplies_cors():
    """기존 버킷도 CORS 가 매번 재적용 (idempotent)."""
    from app.services import s3 as s3_svc

    fake = MagicMock()
    fake.head_bucket.return_value = {}
    s3_svc.ensure_bucket(fake, "test-quarantine")

    fake.create_bucket.assert_not_called()
    fake.put_bucket_cors.assert_called_once()


def test_ensure_bucket_creates_when_missing_then_cors():
    """버킷 부재 시 create_bucket → put_bucket_cors 순으로 호출."""
    from botocore.exceptions import ClientError

    from app.services import s3 as s3_svc

    fake = MagicMock()
    fake.head_bucket.side_effect = ClientError({"Error": {"Code": "NoSuchBucket"}}, "HeadBucket")
    s3_svc.ensure_bucket(fake, "test-quarantine")

    fake.create_bucket.assert_called_once_with(Bucket="test-quarantine")
    fake.put_bucket_cors.assert_called_once()
