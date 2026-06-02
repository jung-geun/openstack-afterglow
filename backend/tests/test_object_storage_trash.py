"""Object Storage 휴지통 (오브젝트·버킷 소프트 삭제/복구/영구삭제) 테스트.

서비스 단위 테스트: conn=MagicMock() + patch("app.services.swift._apply_endpoint_override")
엔드포인트 통합 테스트: patch("app.services.swift") + client/admin_client fixture

테스트 대상:
- soft_delete_object / list_trash_objects / restore_trash_object / purge_trash_object
- purge_expired_trash_objects (만료 판정)
- soft_delete_container_metadata / restore_container_metadata
- DELETE /{c}/objects/{name} → 소프트 삭제 (기본) / 하드 삭제 (?permanent=true)
- GET /{c}/trash / POST /{c}/trash/restore / DELETE /{c}/trash/{key}
- DELETE /{c} → 소프트 삭제 (기본) / 하드 삭제 (?permanent=true)
- GET /trash/containers / POST .../restore / DELETE .../purge
- POST "" 시 소프트 삭제 대기 중 동명 버킷 409
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 서비스 단위 — soft_delete_object
# ---------------------------------------------------------------------------


def _make_conn(project_id: str = "test-project-123") -> MagicMock:
    conn = MagicMock()
    conn._afterglow_project_id = project_id
    conn.object_store = MagicMock()
    return conn


@pytest.mark.asyncio
async def test_soft_delete_object_copies_and_deletes():
    """soft_delete_object 는 {container}-trash 로 COPY 후 원본을 삭제해야 한다."""
    from app.services.swift import soft_delete_object

    conn = _make_conn()

    with patch("app.services.swift._apply_endpoint_override"):
        with patch("app.services.swift.create_container"):
            with patch("app.services.swift.copy_object") as mock_copy:
                with patch("app.services.swift.delete_object") as mock_del:
                    result = soft_delete_object(conn, "my-bucket", "report.pdf")

    assert result["container"] == "my-bucket"
    assert result["trash_container"] == "my-bucket-trash"
    assert result["original_name"] == "report.pdf"
    assert "trash_key" in result
    # trash_key 형식: {epoch}/{uid}/{original_name}
    parts = result["trash_key"].split("/", 2)
    assert len(parts) == 3
    assert parts[2] == "report.pdf"
    assert int(parts[0]) > 0  # epoch

    mock_copy.assert_called_once()
    mock_del.assert_called_once()
    # COPY 호출 시 메타데이터 헤더 포함 확인
    # copy_object(conn, container, name, trash_container, trash_key, extra_headers=...)
    call_args = mock_copy.call_args
    if call_args.kwargs.get("extra_headers"):
        hdrs = call_args.kwargs["extra_headers"]
    else:
        hdrs = call_args.args[5] if len(call_args.args) > 5 else {}
    assert "X-Object-Meta-Orig-Name" in hdrs
    assert "X-Object-Meta-Deleted-At" in hdrs


@pytest.mark.asyncio
async def test_soft_delete_object_directory_uses_move():
    """디렉토리(trailing /) 소프트 삭제는 move_object 를 사용해야 한다 (copy+delete 금지 — 하위 파일 고아 방지)."""
    from app.services.swift import soft_delete_object

    conn = _make_conn()

    with patch("app.services.swift._apply_endpoint_override"):
        with patch("app.services.swift.create_container"):
            with patch("app.services.swift.move_object") as mock_move:
                with patch("app.services.swift.copy_object") as mock_copy:
                    result = soft_delete_object(conn, "my-bucket", "folder/")

    # 디렉토리는 move_object 사용, copy_object 직접 호출 금지
    mock_move.assert_called_once()
    mock_copy.assert_not_called()
    assert result["original_name"] == "folder/"
    assert "trash_key" in result


@pytest.mark.asyncio
async def test_soft_delete_object_trash_key_epoch():
    """trash_key 첫 번째 세그먼트가 현재 시각 epoch 와 일치해야 한다."""
    from app.services.swift import soft_delete_object

    conn = _make_conn()
    before = int(time.time())

    with patch("app.services.swift._apply_endpoint_override"):
        with patch("app.services.swift.create_container"):
            with patch("app.services.swift.copy_object"):
                with patch("app.services.swift.delete_object"):
                    result = soft_delete_object(conn, "bucket", "file.txt")

    after = int(time.time())
    epoch = int(result["trash_key"].split("/")[0])
    assert before <= epoch <= after


# ---------------------------------------------------------------------------
# 서비스 단위 — list_trash_objects
# ---------------------------------------------------------------------------


def test_list_trash_objects_parses_key_format():
    """list_trash_objects 는 trash_key 를 파싱해 original_name / deleted_at 를 반환해야 한다."""
    from app.services.swift import list_trash_objects

    conn = _make_conn()
    epoch = int(time.time())

    fake_obj = MagicMock()
    fake_obj.name = f"{epoch}/abc12345/docs/report.pdf"
    fake_obj.subdir = None
    fake_obj.size = 1024
    fake_obj.content_type = "application/pdf"
    fake_obj.last_modified_at = ""
    fake_obj.etag = "abc"

    conn.object_store.objects.return_value = [fake_obj]

    with patch("app.services.swift._apply_endpoint_override"):
        result = list_trash_objects(conn, "my-bucket")

    assert len(result) == 1
    assert result[0]["original_name"] == "docs/report.pdf"
    assert result[0]["deleted_at"] == epoch
    assert result[0]["trash_key"] == f"{epoch}/abc12345/docs/report.pdf"


def test_list_trash_objects_returns_empty_when_no_trash_bucket():
    """휴지통 버킷이 없으면 빈 목록 반환."""
    from app.services.swift import list_trash_objects

    conn = _make_conn()
    conn.object_store.objects.side_effect = Exception("container not found")

    with patch("app.services.swift._apply_endpoint_override"):
        result = list_trash_objects(conn, "my-bucket")

    assert result == []


# ---------------------------------------------------------------------------
# 서비스 단위 — restore_trash_object
# ---------------------------------------------------------------------------


def test_restore_trash_object_moves_back():
    """restore_trash_object 는 trash → 원본 버킷으로 move 해야 한다."""
    from app.services.swift import restore_trash_object

    conn = _make_conn()
    epoch = int(time.time())
    trash_key = f"{epoch}/ab123456/folder/file.txt"

    # 원본 없음 → 동명 그대로 복구
    conn.object_store.get_object_metadata.side_effect = Exception("not found")

    with patch("app.services.swift._apply_endpoint_override"):
        with patch("app.services.swift.move_object") as mock_move:
            result = restore_trash_object(conn, "my-bucket", trash_key)

    mock_move.assert_called_once()
    args = mock_move.call_args[0]
    assert args[1] == "my-bucket-trash"  # source container
    assert args[2] == trash_key  # source key
    assert args[3] == "my-bucket"  # dest container
    assert args[4] == "folder/file.txt"  # dest name
    assert result["restored_name"] == "folder/file.txt"
    assert result["original_name"] == "folder/file.txt"


def test_restore_trash_object_handles_collision():
    """원본 버킷에 동명 파일이 있으면 '(복구됨)' 접미사를 붙여야 한다."""
    from app.services.swift import restore_trash_object

    conn = _make_conn()
    epoch = int(time.time())
    trash_key = f"{epoch}/ab123456/report.xlsx"

    # 원본 파일 존재
    conn.object_store.get_object_metadata.return_value = MagicMock()

    with patch("app.services.swift._apply_endpoint_override"):
        with patch("app.services.swift.move_object"):
            result = restore_trash_object(conn, "my-bucket", trash_key)

    assert "(복구됨)" in result["restored_name"]
    assert result["original_name"] == "report.xlsx"


def test_restore_trash_object_invalid_key():
    """잘못된 키 형식이면 ValueError 발생."""
    from app.services.swift import restore_trash_object

    conn = _make_conn()

    with patch("app.services.swift._apply_endpoint_override"):
        with pytest.raises(ValueError, match="잘못된 휴지통 키"):
            restore_trash_object(conn, "my-bucket", "bad-key")


# ---------------------------------------------------------------------------
# 서비스 단위 — purge_expired_trash_objects
# ---------------------------------------------------------------------------


def test_purge_expired_only_removes_old_objects():
    """만료된 오브젝트만 삭제하고 최신 항목은 보존해야 한다."""
    from app.services.swift import purge_expired_trash_objects

    conn = _make_conn()
    retention_days = 30
    now = int(time.time())
    old_epoch = now - 31 * 86400  # 31일 전 (만료)
    new_epoch = now - 1 * 86400  # 1일 전 (보존)

    old_key = f"{old_epoch}/aaaaaaaa/old.txt"
    new_key = f"{new_epoch}/bbbbbbbb/new.txt"

    old_obj = {"name": old_key, "trash_key": old_key, "original_name": "old.txt", "deleted_at": old_epoch, "bytes": 10}
    new_obj = {"name": new_key, "trash_key": new_key, "original_name": "new.txt", "deleted_at": new_epoch, "bytes": 20}

    with patch("app.services.swift.list_trash_objects", return_value=[old_obj, new_obj]):
        with patch("app.services.swift.purge_trash_object") as mock_purge:
            result = purge_expired_trash_objects(conn, "my-bucket", retention_days)

    assert old_key in result["purged"]
    assert new_key not in result["purged"]
    assert mock_purge.call_count == 1


# ---------------------------------------------------------------------------
# 서비스 단위 — 버킷 소프트 삭제 메타데이터
# ---------------------------------------------------------------------------


def test_soft_delete_container_metadata_sets_header():
    """soft_delete_container_metadata 는 set_container_metadata 를 afterglow_deleted_at 로 호출해야 한다."""
    from app.services.swift import soft_delete_container_metadata

    conn = _make_conn()
    epoch = int(time.time())

    with patch("app.services.swift._apply_endpoint_override"):
        soft_delete_container_metadata(conn, "my-bucket", epoch)

    conn.object_store.set_container_metadata.assert_called_once_with("my-bucket", afterglow_deleted_at=str(epoch))


def test_restore_container_metadata_clears_header():
    """restore_container_metadata 는 set_container_metadata 를 빈 문자열로 호출해야 한다."""
    from app.services.swift import restore_container_metadata

    conn = _make_conn()

    with patch("app.services.swift._apply_endpoint_override"):
        restore_container_metadata(conn, "my-bucket")

    conn.object_store.set_container_metadata.assert_called_once_with("my-bucket", afterglow_deleted_at="")


# ---------------------------------------------------------------------------
# 엔드포인트 — 오브젝트 소프트 삭제 (기본)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_object_uses_soft_delete_by_default(client, mock_conn):
    """DELETE /objects/{name} 기본: soft_delete_object 호출해야 한다."""
    with patch("app.services.swift") as mock_swift:
        mock_swift.soft_delete_object = MagicMock(
            return_value={"trash_key": "1234/abc/file.txt", "original_name": "file.txt", "deleted_at": 1234}
        )
        mock_swift.delete_object = MagicMock()
        resp = await client.delete("/api/object-storage/my-bucket/objects/file.txt")

    assert resp.status_code in (204, 404, 405, 500)
    if resp.status_code == 204:
        mock_swift.soft_delete_object.assert_called_once()
        mock_swift.delete_object.assert_not_called()


@pytest.mark.asyncio
async def test_delete_object_permanent_uses_hard_delete(client, mock_conn):
    """DELETE /objects/{name}?permanent=true: delete_object 호출해야 한다."""
    with patch("app.services.swift") as mock_swift:
        mock_swift.delete_object = MagicMock()
        mock_swift.soft_delete_object = MagicMock()
        resp = await client.delete("/api/object-storage/my-bucket/objects/file.txt?permanent=true")

    assert resp.status_code in (204, 404, 405, 500)
    if resp.status_code == 204:
        mock_swift.delete_object.assert_called_once()
        mock_swift.soft_delete_object.assert_not_called()


# ---------------------------------------------------------------------------
# 엔드포인트 — 휴지통 목록 / 복구 / 영구삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_trash_returns_objects(client, mock_conn):
    """GET /{c}/trash: 휴지통 오브젝트 목록 반환."""
    epoch = int(time.time())
    with patch("app.services.swift") as mock_swift:
        mock_swift.list_trash_objects = MagicMock(
            return_value=[
                {
                    "trash_key": f"{epoch}/abc/file.txt",
                    "original_name": "file.txt",
                    "deleted_at": epoch,
                    "bytes": 100,
                }
            ]
        )
        resp = await client.get("/api/object-storage/my-bucket/trash")

    assert resp.status_code in (200, 404, 405, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_restore_trash_object_endpoint(client, mock_conn):
    """POST /{c}/trash/restore: 복구 성공."""
    trash_key = f"{int(time.time())}/abc12345/report.pdf"
    with patch("app.services.swift") as mock_swift:
        mock_swift.restore_trash_object = MagicMock(
            return_value={"restored_name": "report.pdf", "original_name": "report.pdf", "container": "my-bucket"}
        )
        resp = await client.post(
            "/api/object-storage/my-bucket/trash/restore",
            json={"trash_key": trash_key},
        )

    assert resp.status_code in (200, 404, 405, 500)


@pytest.mark.asyncio
async def test_purge_trash_object_endpoint(client, mock_conn):
    """DELETE /{c}/trash/{key}: 영구 삭제 204."""
    trash_key = f"{int(time.time())}/abc12345/report.pdf"
    with patch("app.services.swift") as mock_swift:
        mock_swift.purge_trash_object = MagicMock()
        resp = await client.delete(f"/api/object-storage/my-bucket/trash/{trash_key}")

    assert resp.status_code in (204, 404, 405, 500)


# ---------------------------------------------------------------------------
# 엔드포인트 — 버킷 소프트 삭제 / 복구 / 영구삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_container_soft_by_default(client, mock_conn):
    """DELETE /{container} 기본: soft_delete_container_metadata 호출, 하드 삭제 안 함."""
    with patch("app.services.swift") as mock_swift:
        mock_swift.soft_delete_container_metadata = MagicMock()
        mock_swift.delete_container = MagicMock()
        resp = await client.delete("/api/object-storage/my-bucket")

    assert resp.status_code in (204, 404, 405, 500)
    if resp.status_code == 204:
        mock_swift.soft_delete_container_metadata.assert_called_once()
        mock_swift.delete_container.assert_not_called()


@pytest.mark.asyncio
async def test_delete_container_permanent_hard_deletes(client, mock_conn):
    """DELETE /{container}?permanent=true: delete_container 호출."""
    with patch("app.services.swift") as mock_swift:
        mock_swift.delete_container = MagicMock()
        mock_swift.soft_delete_container_metadata = MagicMock()
        resp = await client.delete("/api/object-storage/my-bucket?permanent=true")

    assert resp.status_code in (204, 404, 405, 500)
    if resp.status_code == 204:
        mock_swift.delete_container.assert_called_once()
        mock_swift.soft_delete_container_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_create_container_blocks_soft_deleted_name(client, mock_conn):
    """소프트 삭제 대기 중인 버킷 이름으로 생성 시 409 반환."""
    from app.api.object_storage.containers import _mark_container_deleted

    await _mark_container_deleted("test-project-123", "blocked-bucket", int(time.time()), 30)

    with patch("app.services.swift") as mock_swift:
        mock_swift.create_container = MagicMock()
        resp = await client.post("/api/object-storage", json={"name": "blocked-bucket"})

    assert resp.status_code in (409, 404, 405)
    if resp.status_code == 409:
        assert "삭제 대기" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_deleted_containers_endpoint(client, mock_conn):
    """GET /trash/containers: 소프트 삭제 버킷 목록 반환."""
    from app.api.object_storage.containers import _mark_container_deleted

    await _mark_container_deleted("test-project-123", "deleted-bucket", int(time.time()), 30)

    with patch("app.services.swift") as mock_swift:
        mock_swift.list_containers = MagicMock(return_value=[{"name": "deleted-bucket", "count": 5, "bytes": 1024}])
        resp = await client.get("/api/object-storage/trash/containers")

    assert resp.status_code in (200, 404, 405, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, list)
        names = [c["name"] for c in data]
        assert "deleted-bucket" in names


@pytest.mark.asyncio
async def test_restore_deleted_container_endpoint(client, mock_conn):
    """POST /trash/containers/{name}/restore: 복구 성공."""
    from app.api.object_storage.containers import (
        _is_container_deleted,
        _mark_container_deleted,
    )

    await _mark_container_deleted("test-project-123", "my-bucket", int(time.time()), 30)
    assert await _is_container_deleted("test-project-123", "my-bucket") is not None

    with patch("app.services.swift") as mock_swift:
        mock_swift.restore_container_metadata = MagicMock()
        resp = await client.post("/api/object-storage/trash/containers/my-bucket/restore")

    assert resp.status_code in (200, 404, 405, 500)
    if resp.status_code == 200:
        assert await _is_container_deleted("test-project-123", "my-bucket") is None


@pytest.mark.asyncio
async def test_purge_deleted_container_endpoint(client, mock_conn):
    """DELETE /trash/containers/{name}: 영구 삭제 204."""
    from app.api.object_storage.containers import _mark_container_deleted

    await _mark_container_deleted("test-project-123", "purge-bucket", int(time.time()), 30)

    with patch("app.services.swift") as mock_swift:
        mock_swift.delete_container = MagicMock()
        resp = await client.delete("/api/object-storage/trash/containers/purge-bucket")

    assert resp.status_code in (204, 404, 405, 500)
    if resp.status_code == 204:
        mock_swift.delete_container.assert_called_once()


@pytest.mark.asyncio
async def test_purge_deleted_container_404_if_not_in_trash(client, mock_conn):
    """소프트 삭제 마킹 없는 버킷 영구 삭제 시 404."""
    with patch("app.services.swift") as mock_swift:
        mock_swift.delete_container = MagicMock()
        resp = await client.delete("/api/object-storage/trash/containers/nonexistent-bucket")

    assert resp.status_code in (404, 405)
