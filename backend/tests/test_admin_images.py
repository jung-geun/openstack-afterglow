"""admin_images.py 엔드포인트 단위 테스트."""

from types import SimpleNamespace

import pytest


def _make_image(img_id: str, name: str, **extra) -> SimpleNamespace:
    base = {
        "id": img_id,
        "name": name,
        "status": "active",
        "size": 0,
        "min_disk": 0,
        "min_ram": 0,
        "disk_format": "raw",
        "os_distro": None,
        "visibility": "public",
        "owner": "owner-1",
        "created_at": None,
        "is_protected": False,
    }
    base.update(extra)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_list_admin_images_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/images")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_admin_images_allowed(admin_client, mock_conn):
    mock_conn.image.images.return_value = iter([])
    resp = await admin_client.get("/api/admin/images")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_list_admin_images_search_substring_case_insensitive(admin_client, mock_conn):
    """search='u'는 ubuntu/Windows-Update/centos 중 'u' 포함 이미지를 모두 반환해야 함."""
    images = [
        _make_image("1", "ubuntu-24.04"),
        _make_image("2", "Windows-Update-2024"),
        _make_image("3", "centos-9"),
        _make_image("4", "fedora-39"),
    ]
    mock_conn.image.images.return_value = iter(images)
    resp = await admin_client.get("/api/admin/images?search=u")
    assert resp.status_code == 200
    body = resp.json()
    names = {item["name"] for item in body["items"]}
    assert names == {"ubuntu-24.04", "Windows-Update-2024"}


@pytest.mark.asyncio
async def test_list_admin_images_search_no_match(admin_client, mock_conn):
    images = [
        _make_image("1", "ubuntu-24.04"),
        _make_image("2", "centos-9"),
    ]
    mock_conn.image.images.return_value = iter(images)
    resp = await admin_client.get("/api/admin/images?search=zzznoexist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["count"] == 0
    assert body["next_marker"] is None


@pytest.mark.asyncio
async def test_list_admin_images_search_pagination_with_marker(admin_client, mock_conn):
    """검색 결과가 limit 보다 많을 때 marker 기반 페이지네이션."""
    images = [_make_image(f"id-{i}", f"ubuntu-{i}") for i in range(5)]
    mock_conn.image.images.return_value = iter(images)
    resp = await admin_client.get("/api/admin/images?search=ubuntu&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert [item["id"] for item in body["items"]] == ["id-0", "id-1"]
    assert body["next_marker"] == "id-1"

    # 두 번째 페이지
    mock_conn.image.images.return_value = iter(images)
    resp2 = await admin_client.get("/api/admin/images?search=ubuntu&limit=2&marker=id-1")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert [item["id"] for item in body2["items"]] == ["id-2", "id-3"]
    assert body2["next_marker"] == "id-3"


@pytest.mark.asyncio
async def test_list_admin_images_search_does_not_pass_name_to_glance(admin_client, mock_conn):
    """search 시 Glance에 name= 정확매칭 인자를 넘기면 안 된다 (substring은 클라이언트 필터)."""
    images = [_make_image("1", "ubuntu-24.04")]
    mock_conn.image.images.return_value = iter(images)
    resp = await admin_client.get("/api/admin/images?search=ub")
    assert resp.status_code == 200
    # Glance 호출 인자 검사: name 키가 없어야 함
    _, called_kwargs = mock_conn.image.images.call_args
    assert "name" not in called_kwargs


@pytest.mark.asyncio
async def test_get_admin_image_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/images/img-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_admin_image_requires_admin(non_admin_client):
    resp = await non_admin_client.patch("/api/admin/images/img-1", json={"name": "new"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_image_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/images/img-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_image_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/images/img-1/deactivate")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reactivate_image_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/images/img-1/reactivate")
    assert resp.status_code == 403
