"""GPU Quota 관리 API 단위 테스트 (admin.py 내 GPU quota 엔드포인트).

검증 항목:
1. 모든 GPU quota 엔드포인트: non-admin → 403
2. DB 미초기화 시 → 503
3. 쿼터 계산 로직 (available = limit - in_use, -1 = 무제한)
4. 정상 응답 (admin 허용, 200/204)
"""

from unittest.mock import AsyncMock, patch

import pytest

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 인증 (admin-only) 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_gpu_aliases_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/v1/admin/gpu-quotas/proj-1", json={"gpu_type": "RTX3090", "limit": 2})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/v1/admin/gpu-quotas/proj-1/RTX3090")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB 미초기화 시 503 응답 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_set_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_gpu_quotas_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_set_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.put("/api/v1/admin/gpu-quotas/proj-1", json={"gpu_type": "RTX3090", "limit": 2})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_delete_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.delete("/api/v1/admin/gpu-quotas/proj-1/RTX3090")
    assert resp.status_code == 503


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GPU alias 목록 조회 (admin 허용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_gpu_aliases_allowed(admin_client):
    with patch(
        "app.services.gpu_quota.get_all_gpu_aliases",
        new=AsyncMock(return_value=["RTX3090", "RTX4090"]),
    ):
        resp = await admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 200
    assert resp.json() == {"aliases": ["RTX3090", "RTX4090"]}


@pytest.mark.asyncio
async def test_get_gpu_aliases_empty(admin_client):
    with patch(
        "app.services.gpu_quota.get_all_gpu_aliases",
        new=AsyncMock(return_value=[]),
    ):
        resp = await admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 200
    assert resp.json() == {"aliases": []}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기본 GPU quota CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_success(admin_client):
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_project_gpu_quotas",
            new=AsyncMock(return_value=[{"gpu_type": "RTX3090", "limit": 4, "id": 1}]),
        ):
            resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [{"gpu_type": "RTX3090", "limit": 4}]


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_empty(admin_client):
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_project_gpu_quotas",
            new=AsyncMock(return_value=[]),
        ):
            resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_set_default_gpu_quota_success(admin_client):
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.set_project_gpu_quota",
            new=AsyncMock(return_value={"project_id": "__default__", "gpu_type": "RTX3090", "limit": 4}),
        ):
            resp = await admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu_type"] == "RTX3090"
    assert data["limit"] == 4


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_success(admin_client):
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.delete_project_gpu_quota",
            new=AsyncMock(return_value=None),
        ):
            resp = await admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 204


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프로젝트별 GPU quota CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_set_gpu_quota_success(admin_client):
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.set_project_gpu_quota",
            new=AsyncMock(return_value={"project_id": "proj-1", "gpu_type": "RTX3090", "limit": 2}),
        ):
            resp = await admin_client.put("/api/v1/admin/gpu-quotas/proj-1", json={"gpu_type": "RTX3090", "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "proj-1"
    assert data["gpu_type"] == "RTX3090"
    assert data["limit"] == 2


@pytest.mark.asyncio
async def test_delete_gpu_quota_success(admin_client):
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.delete_project_gpu_quota",
            new=AsyncMock(return_value=None),
        ):
            resp = await admin_client.delete("/api/v1/admin/gpu-quotas/proj-1/RTX3090")
    assert resp.status_code == 204


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 쿼터 계산 로직 테스트 (available = limit - in_use / -1 = 무제한)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_gpu_quotas_available_calculation(admin_client):
    """limit - in_use 계산 검증: available = limit - in_use."""
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_all_gpu_aliases",
            new=AsyncMock(return_value=["RTX3090"]),
        ):
            with patch(
                "app.services.gpu_quota.get_effective_gpu_quotas",
                new=AsyncMock(return_value={"RTX3090": 4}),
            ):
                with patch(
                    "app.services.gpu_quota.get_project_gpu_usage",
                    new=AsyncMock(return_value={"RTX3090": 1}),
                ):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["gpu_type"] == "RTX3090"
    assert item["limit"] == 4
    assert item["in_use"] == 1
    assert item["available"] == 3  # 4 - 1


@pytest.mark.asyncio
async def test_get_gpu_quotas_available_zero(admin_client):
    """quota를 모두 사용한 경우 available = 0."""
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_all_gpu_aliases",
            new=AsyncMock(return_value=["RTX3090"]),
        ):
            with patch(
                "app.services.gpu_quota.get_effective_gpu_quotas",
                new=AsyncMock(return_value={"RTX3090": 2}),
            ):
                with patch(
                    "app.services.gpu_quota.get_project_gpu_usage",
                    new=AsyncMock(return_value={"RTX3090": 2}),
                ):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["available"] == 0  # 2 - 2


@pytest.mark.asyncio
async def test_get_gpu_quotas_unlimited(admin_client):
    """limit = -1 (무제한)일 때 available = -1 검증."""
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_all_gpu_aliases",
            new=AsyncMock(return_value=["RTX4090"]),
        ):
            with patch(
                "app.services.gpu_quota.get_effective_gpu_quotas",
                new=AsyncMock(return_value={"RTX4090": -1}),
            ):
                with patch(
                    "app.services.gpu_quota.get_project_gpu_usage",
                    new=AsyncMock(return_value={"RTX4090": 5}),
                ):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["gpu_type"] == "RTX4090"
    assert item["limit"] == -1
    assert item["in_use"] == 5
    assert item["available"] == -1  # 무제한이면 available도 -1


@pytest.mark.asyncio
async def test_get_gpu_quotas_multiple_types(admin_client):
    """여러 GPU 타입에 대한 quota 계산 검증."""
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_all_gpu_aliases",
            new=AsyncMock(return_value=["RTX3090", "RTX4090"]),
        ):
            with patch(
                "app.services.gpu_quota.get_effective_gpu_quotas",
                new=AsyncMock(return_value={"RTX3090": 4, "RTX4090": -1}),
            ):
                with patch(
                    "app.services.gpu_quota.get_project_gpu_usage",
                    new=AsyncMock(return_value={"RTX3090": 2, "RTX4090": 3}),
                ):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    data = {item["gpu_type"]: item for item in resp.json()}
    assert data["RTX3090"]["available"] == 2  # 4 - 2
    assert data["RTX4090"]["available"] == -1  # 무제한


@pytest.mark.asyncio
async def test_get_gpu_quotas_no_quota_set(admin_client):
    """quota 미설정 GPU alias는 limit=0, available=0으로 반환."""
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_all_gpu_aliases",
            new=AsyncMock(return_value=["RTX3090"]),
        ):
            with patch(
                "app.services.gpu_quota.get_effective_gpu_quotas",
                new=AsyncMock(return_value={}),  # 미설정
            ):
                with patch(
                    "app.services.gpu_quota.get_project_gpu_usage",
                    new=AsyncMock(return_value={}),
                ):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["gpu_type"] == "RTX3090"
    assert item["limit"] == 0
    assert item["in_use"] == 0
    assert item["available"] == 0


@pytest.mark.asyncio
async def test_get_gpu_quotas_union_of_alias_sources(admin_client):
    """aliases, effective, usage 세 소스의 합집합으로 결과를 반환."""
    # aliases에는 없지만 usage에는 있는 타입도 포함되어야 함
    with patch("app.database.is_db_available", return_value=True):
        with patch(
            "app.services.gpu_quota.get_all_gpu_aliases",
            new=AsyncMock(return_value=["RTX3090"]),
        ):
            with patch(
                "app.services.gpu_quota.get_effective_gpu_quotas",
                new=AsyncMock(return_value={"RTX3090": 4, "GTX1080": 1}),
            ):
                with patch(
                    "app.services.gpu_quota.get_project_gpu_usage",
                    new=AsyncMock(return_value={"RTX3090": 1}),
                ):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    types = {item["gpu_type"] for item in resp.json()}
    assert "RTX3090" in types
    assert "GTX1080" in types


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# circuit breaker 가드 — is_db_available() False 시 빈 결과
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_returns_empty_when_db_unavailable():
    """is_db_available() False 시 get_project_gpu_quotas가 즉시 빈 목록을 반환한다."""
    with patch("app.services.gpu_quota.is_db_available", return_value=False):
        from app.services.gpu_quota import get_project_gpu_quotas

        result = await get_project_gpu_quotas("test-project")
    assert result == []


@pytest.mark.asyncio
async def test_get_effective_gpu_quotas_returns_empty_when_db_unavailable():
    """is_db_available() False 시 get_effective_gpu_quotas가 즉시 빈 dict를 반환한다."""
    with patch("app.services.gpu_quota.is_db_available", return_value=False):
        from app.services.gpu_quota import get_effective_gpu_quotas

        result = await get_effective_gpu_quotas("test-project")
    assert result == {}
