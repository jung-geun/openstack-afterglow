"""Direct upload (S3 multipart) + quarantine 흐름 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

_USER_ID = "test-user-123"
_PROJECT_ID = "test-project-123"


# ---------------------------------------------------------------------------
# calc_parts 단위 테스트
# ---------------------------------------------------------------------------


def test_calc_parts_small_file_single():
    from app.services.s3 import calc_parts

    count, _ = calc_parts(1024)
    assert count == 1


def test_calc_parts_50mib_threshold():
    from app.services.s3 import calc_parts

    count, _ = calc_parts(40 * 1024 * 1024)
    assert count == 1


def test_calc_parts_8gib_chunks():
    from app.services.s3 import calc_parts

    count, size = calc_parts(8 * 1024**3)
    assert 1 < count <= 1000
    assert size >= 5 * 1024 * 1024


def test_calc_parts_huge_caps_at_max():
    from app.services.s3 import calc_parts

    count, size = calc_parts(5 * 1024**4)  # 5 TiB
    assert count == 1000
    assert size >= 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# upload/init 엔드포인트 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_init_creates_quarantine_and_returns_parts(client, mock_conn, monkeypatch):
    from botocore.exceptions import ClientError

    fake_s3 = MagicMock()
    fake_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadBucket")
    fake_s3.create_multipart_upload.return_value = {"UploadId": "up-1"}
    fake_s3.generate_presigned_url.side_effect = lambda op, Params=None, ExpiresIn=None, HttpMethod=None, **kw: (
        f"https://rgw/p{(Params or {}).get('PartNumber', 0)}"
    )

    monkeypatch.setattr("app.api.object_storage.upload.s3_svc.get_user_s3_client", lambda *a, **kw: fake_s3)
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        lambda *a, **kw: {"name": "test"},
    )
    monkeypatch.setattr("app.api.object_storage.upload._save_tx", AsyncMock())

    resp = await client.post(
        "/api/object-storage/test/upload/init",
        json={"object_name": "Music.zip", "content_type": "application/zip", "size": 8 * 1024**3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quarantine_bucket"] == "test-quarantine"
    assert body["upload_id"] == "up-1"
    assert len(body["parts"]) > 1
    fake_s3.create_bucket.assert_called_once_with(Bucket="test-quarantine")
    fake_s3.put_bucket_cors.assert_called_once()


@pytest.mark.asyncio
async def test_upload_init_rejects_nonexistent_container(client, mock_conn, monkeypatch):
    monkeypatch.setattr(
        "app.api.object_storage.upload.swift_svc.get_container_metadata",
        MagicMock(side_effect=Exception("not found")),
    )

    resp = await client.post(
        "/api/object-storage/other-bucket/upload/init",
        json={"object_name": "x.bin", "content_type": "application/octet-stream", "size": 1024},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# upload/complete 엔드포인트 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_complete_copies_to_target_then_deletes_quarantine(client, mock_conn, monkeypatch):
    fake_s3 = MagicMock()
    monkeypatch.setattr("app.api.object_storage.upload.s3_svc.get_user_s3_client", lambda *a, **kw: fake_s3)

    async def fake_get_tx(tx_id):
        return {
            "user_id": _USER_ID,
            "project_id": _PROJECT_ID,
            "target_bucket": "test",
            "object_name": "Music.zip",
            "quarantine_bucket": "test-quarantine",
            "upload_id": "up-1",
            "size": 1024,
            "content_type": "application/zip",
            "part_count": 1,
            "part_size": 1024,
        }

    monkeypatch.setattr("app.api.object_storage.upload._get_tx", fake_get_tx)
    monkeypatch.setattr("app.api.object_storage.upload._del_tx", AsyncMock())

    resp = await client.post(
        "/api/object-storage/test/upload/complete",
        json={"transaction_id": "tx-1", "parts": [{"part_number": 1, "etag": '"abc"'}]},
    )
    assert resp.status_code == 200
    fake_s3.complete_multipart_upload.assert_called_once()
    fake_s3.copy.assert_called_once()
    fake_s3.delete_object.assert_called_once_with(Bucket="test-quarantine", Key="Music.zip")


@pytest.mark.asyncio
async def test_upload_complete_rejects_other_user(client, mock_conn, monkeypatch):
    async def fake_get_tx(tx_id):
        return {
            "user_id": "other-user",
            "project_id": "other-proj",
            "target_bucket": "test",
            "object_name": "x",
            "quarantine_bucket": "test-quarantine",
            "upload_id": "u",
            "size": 1,
            "part_count": 1,
            "part_size": 1,
        }

    monkeypatch.setattr("app.api.object_storage.upload._get_tx", fake_get_tx)

    resp = await client.post(
        "/api/object-storage/test/upload/complete",
        json={"transaction_id": "tx-1", "parts": []},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_complete_unknown_tx_404(client, mock_conn, monkeypatch):
    monkeypatch.setattr("app.api.object_storage.upload._get_tx", AsyncMock(return_value=None))

    resp = await client.post(
        "/api/object-storage/test/upload/complete",
        json={"transaction_id": "missing", "parts": []},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# upload/abort 엔드포인트 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_abort_calls_s3_abort(client, mock_conn, monkeypatch):
    fake_s3 = MagicMock()
    monkeypatch.setattr("app.api.object_storage.upload.s3_svc.get_user_s3_client", lambda *a, **kw: fake_s3)

    async def fake_get_tx(tx_id):
        return {
            "user_id": _USER_ID,
            "project_id": _PROJECT_ID,
            "target_bucket": "test",
            "object_name": "Music.zip",
            "quarantine_bucket": "test-quarantine",
            "upload_id": "up-1",
            "size": 1,
            "part_count": 1,
            "part_size": 1,
        }

    monkeypatch.setattr("app.api.object_storage.upload._get_tx", fake_get_tx)
    monkeypatch.setattr("app.api.object_storage.upload._del_tx", AsyncMock())

    resp = await client.post(
        "/api/object-storage/test/upload/abort",
        json={"transaction_id": "tx-1"},
    )
    assert resp.status_code == 200
    fake_s3.abort_multipart_upload.assert_called_once()


@pytest.mark.asyncio
async def test_upload_abort_unknown_tx_ok(client, mock_conn, monkeypatch):
    """트랜잭션 없어도 abort는 200 반환 (idempotent)."""
    monkeypatch.setattr("app.api.object_storage.upload._get_tx", AsyncMock(return_value=None))

    resp = await client.post(
        "/api/object-storage/test/upload/abort",
        json={"transaction_id": "missing"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CORS 다중 origin + ensure_bucket idempotent 재적용 테스트 (Phase 8.3)
# ---------------------------------------------------------------------------


def test_put_bucket_cors_uses_wildcard_origin():
    """_put_bucket_cors 가 AllowedOrigins=["*"] 를 사용 (presigned URL 은 서명으로 보호)."""
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
    """기존 버킷(head_bucket 성공)도 CORS 가 매번 재적용되어야 한다."""
    from app.services import s3 as s3_svc

    fake = MagicMock()
    fake.head_bucket.return_value = {}  # 이미 존재
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
