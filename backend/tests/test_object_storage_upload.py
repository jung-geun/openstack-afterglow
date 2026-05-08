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


def test_stream_upload_callback_raises_when_cancel_event_set():
    """cancel_event 가 set 된 상태에서 boto3 Callback 호출 → UploadCanceled raise."""
    import threading

    from app.services import s3 as s3_svc

    captured: dict = {}

    def _capture_call(**kwargs):
        captured.update(kwargs)

    fake = MagicMock()
    fake.upload_fileobj.side_effect = _capture_call

    cancel_event = threading.Event()
    s3_svc.stream_upload_to_quarantine(
        fake, "test-quarantine", "obj.bin", MagicMock(), "text/plain", cancel_event=cancel_event
    )

    callback = captured["Callback"]
    # cancel_event 미설정 → 정상 (no raise)
    callback(1024)
    # cancel_event set → UploadCanceled
    cancel_event.set()
    with pytest.raises(s3_svc.UploadCanceled):
        callback(1024)


def test_stream_upload_no_cancel_event_callback_safe():
    """cancel_event 미전달 시 Callback 은 항상 no-op (raise 안 함)."""
    from app.services import s3 as s3_svc

    captured: dict = {}
    fake = MagicMock()
    fake.upload_fileobj.side_effect = lambda **kw: captured.update(kw)
    s3_svc.stream_upload_to_quarantine(fake, "b", "k", MagicMock(), "text/plain")
    captured["Callback"](1024)  # raise 없어야 함


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


# ---------------------------------------------------------------------------
# 보안 패치 — path traversal sanitize / CORS 화이트리스트 / 크기 cap
# ---------------------------------------------------------------------------


def test_sanitize_object_name_strips_path_traversal():
    """`..` 와 `.` segment 를 제거해 경로 탈출 시도 차단."""
    from app.api.object_storage.containers import _sanitize_object_name

    assert _sanitize_object_name("../../../etc/passwd") == "etc/passwd"
    assert _sanitize_object_name("foo/../bar") == "foo/bar"
    assert _sanitize_object_name("/././etc/foo") == "etc/foo"
    assert _sanitize_object_name("..") == "unnamed"
    assert _sanitize_object_name("/") == "unnamed"


def test_sanitize_object_name_strips_control_chars():
    """제어문자 / NUL / DEL 제거."""
    from app.api.object_storage.containers import _sanitize_object_name

    assert _sanitize_object_name("foo\x00bar") == "foobar"
    assert _sanitize_object_name("foo\nbar") == "foobar"
    assert _sanitize_object_name("foo\x7fbar") == "foobar"


def test_sanitize_object_name_truncates_long():
    """1024자 초과는 잘라낸다."""
    from app.api.object_storage.containers import _sanitize_object_name

    long = "a" * 2000
    out = _sanitize_object_name(long)
    assert len(out) == 1024


def test_put_bucket_cors_uses_origin_whitelist():
    """RGW CORS 가 wildcard 가 아니라 settings.cors_origin_list 화이트리스트를 사용."""
    from unittest.mock import patch

    from app.services import s3 as s3_svc

    fake = MagicMock()
    mock_settings = MagicMock()
    mock_settings.cors_origin_list = ["https://app.example.com", "https://staging.example.com"]
    with patch("app.config.get_settings", return_value=mock_settings):
        s3_svc._put_bucket_cors(fake, "test-bucket")

    fake.put_bucket_cors.assert_called_once()
    rule = fake.put_bucket_cors.call_args.kwargs["CORSConfiguration"]["CORSRules"][0]
    assert rule["AllowedOrigins"] == ["https://app.example.com", "https://staging.example.com"]
    assert "*" not in rule["AllowedOrigins"]
    # AllowedHeaders 도 wildcard 가 아니어야 함
    assert "*" not in rule["AllowedHeaders"]


def test_put_bucket_cors_disables_when_no_whitelist():
    """화이트리스트가 비어 있으면 CORS rule 자체를 제거 (cross-origin 차단)."""
    from unittest.mock import patch

    from app.services import s3 as s3_svc

    fake = MagicMock()
    mock_settings = MagicMock()
    mock_settings.cors_origin_list = []
    with patch("app.config.get_settings", return_value=mock_settings):
        s3_svc._put_bucket_cors(fake, "test-bucket")

    fake.delete_bucket_cors.assert_called_once_with(Bucket="test-bucket")
    fake.put_bucket_cors.assert_not_called()
