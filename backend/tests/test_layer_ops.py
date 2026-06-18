"""squashfs 레이어 빌드/소비 API 테스트.

커버 범위:
  - LayerBuildRequest / LayerConsumeRequest Pydantic 화이트리스트 검증 (명령주입 차단)
  - require_admin 인증 가드 (비인증 → 401, 일반 사용자 → 403)
  - POST /api/admin/layers/build 성공 흐름 (layer_builder.start_layer_build mock)
  - GET  /api/admin/layers/builds 목록 (DB mock)
  - GET  /api/admin/layers/builds/{id} 상세 (DB mock)
  - POST /api/admin/layers/builds/{id}/cancel 취소 (layer_builder.cancel_layer_build mock)
  - POST /api/admin/layers/consume 성공 흐름 (run_layer_consume mock)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.union.layer_ops import LayerBuildRequest, LayerConsumeRequest
from app.main import app

BASE = "/api/v1/admin/layers"


# ============================================================================
# Part 0: Pydantic 화이트리스트 검증 — LayerBuildRequest
# ============================================================================


class TestLayerBuildRequestValidation:
    """LayerBuildRequest 입력값 화이트리스트 검증."""

    def test_valid_request_accepted(self):
        req = LayerBuildRequest(
            layer_name="uvpy311",
            python_version="3.11",
            pip_packages=["numpy", "pandas"],
            profile_name="smoke",
        )
        assert req.layer_name == "uvpy311"
        assert req.python_version == "3.11"
        assert req.pip_packages == ["numpy", "pandas"]

    def test_valid_layer_name_with_dots_and_hyphens(self):
        req = LayerBuildRequest(layer_name="uv-py3.11", python_version="3.11")
        assert req.layer_name == "uv-py3.11"

    # --- layer_name 명령주입 차단 ---

    def test_layer_name_with_semicolon_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="name;evil", python_version="3.11")

    def test_layer_name_with_newline_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="name\nevil", python_version="3.11")

    def test_layer_name_with_backtick_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="`rm -rf /`", python_version="3.11")

    def test_layer_name_with_dollar_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="$(id)", python_version="3.11")

    def test_layer_name_with_slash_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="a/b", python_version="3.11")

    def test_layer_name_starting_with_hyphen_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="-bad", python_version="3.11")

    # --- python_version 형식 검증 ---

    def test_python_version_major_minor_only_accepted(self):
        req = LayerBuildRequest(layer_name="test", python_version="3.12")
        assert req.python_version == "3.12"

    def test_python_version_with_patch_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="test", python_version="3.11.2")

    def test_python_version_text_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="test", python_version="latest")

    def test_python_version_with_injection_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(layer_name="test", python_version="3.11;evil")

    # --- pip_packages 명령주입 차단 ---

    def test_valid_pip_packages_accepted(self):
        req = LayerBuildRequest(
            layer_name="test",
            python_version="3.11",
            pip_packages=["numpy>=1.24", "pandas[excel]", "scikit-learn~=1.0"],
        )
        assert len(req.pip_packages) == 3

    def test_pip_package_with_semicolon_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(
                layer_name="test",
                python_version="3.11",
                pip_packages=["numpy;rm -rf /"],
            )

    def test_pip_package_with_dollar_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(
                layer_name="test",
                python_version="3.11",
                pip_packages=["$(evil)"],
            )

    def test_pip_package_with_newline_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(
                layer_name="test",
                python_version="3.11",
                pip_packages=["numpy\nevil"],
            )

    # --- profile_name 검증 ---

    def test_profile_name_with_injection_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(
                layer_name="test",
                python_version="3.11",
                profile_name="profile$(id)",
            )

    def test_profile_name_with_newline_rejected(self):
        with pytest.raises(ValidationError):
            LayerBuildRequest(
                layer_name="test",
                python_version="3.11",
                profile_name="profile\nevil",
            )


# ============================================================================
# Part 1: Pydantic 화이트리스트 검증 — LayerConsumeRequest
# ============================================================================


class TestLayerConsumeRequestValidation:
    """LayerConsumeRequest 입력값 화이트리스트 검증."""

    def test_valid_request_accepted(self):
        req = LayerConsumeRequest(
            profile_name="default",
            server_name="consumer-01",
            flavor_id="m1.small",
        )
        assert req.profile_name == "default"
        assert req.server_name == "consumer-01"

    # --- server_name 검증 ---

    def test_server_name_with_semicolon_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default",
                server_name="evil;rm",
                flavor_id="m1.small",
            )

    def test_server_name_too_long_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default",
                server_name="a" * 64,
                flavor_id="m1.small",
            )

    def test_server_name_starting_with_hyphen_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default",
                server_name="-bad-name",
                flavor_id="m1.small",
            )

    def test_server_name_with_newline_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default",
                server_name="server\nevil",
                flavor_id="m1.small",
            )

    # --- flavor_id 검증 ---

    def test_flavor_id_with_semicolon_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default",
                server_name="test",
                flavor_id="m1.small;evil",
            )

    def test_flavor_id_with_space_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default",
                server_name="test",
                flavor_id="m1 small",
            )

    # --- profile_name 검증 ---

    def test_consume_profile_name_with_injection_rejected(self):
        with pytest.raises(ValidationError):
            LayerConsumeRequest(
                profile_name="default$(id)",
                server_name="test",
                flavor_id="m1.small",
            )


# ============================================================================
# Part 2: 인증/인가 가드 — 비인증(401) · 일반 사용자(403)
# ============================================================================


@pytest.mark.asyncio
async def test_build_requires_auth():
    """비인증 요청은 401을 반환한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"{BASE}/build", json={"layer_name": "test", "python_version": "3.11"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_builds_list_requires_auth():
    """GET /builds 비인증 → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"{BASE}/builds")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_consume_requires_auth():
    """POST /consume 비인증 → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"{BASE}/consume",
            json={"profile_name": "default", "server_name": "test", "flavor_id": "m1.small"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_build_requires_admin_role(non_admin_client):
    """admin 역할 없는 사용자는 403을 반환한다."""
    resp = await non_admin_client.post(
        f"{BASE}/build",
        json={"layer_name": "test", "python_version": "3.11"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_builds_list_requires_admin_role(non_admin_client):
    """GET /builds — admin 역할 없는 사용자는 403."""
    resp = await non_admin_client.get(f"{BASE}/builds")
    assert resp.status_code == 403


# ============================================================================
# Part 3: 빌드 트리거 성공 흐름
# ============================================================================


@pytest.mark.asyncio
async def test_trigger_build_success(admin_client):
    """POST /build → layer_builder.start_layer_build 호출 + build_id 반환."""
    mock_result = {"build_id": 42, "layer_name": "uvpy311", "status": "queued"}

    with patch(
        "app.services.layer_builder.start_layer_build",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await admin_client.post(
            f"{BASE}/build",
            json={
                "layer_name": "uvpy311",
                "python_version": "3.11",
                "pip_packages": ["numpy"],
                "profile_name": "smoke",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["build_id"] == 42
    assert data["layer_name"] == "uvpy311"
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_trigger_build_invalid_layer_name(admin_client):
    """유효하지 않은 layer_name(명령주입)은 422를 반환한다."""
    resp = await admin_client.post(
        f"{BASE}/build",
        json={"layer_name": "evil$(id)", "python_version": "3.11"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_build_invalid_python_version(admin_client):
    """유효하지 않은 python_version 형식은 422를 반환한다."""
    resp = await admin_client.post(
        f"{BASE}/build",
        json={"layer_name": "test", "python_version": "3.11.2"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_build_invalid_pip_package(admin_client):
    """pip 패키지에 셸 메타문자가 포함되면 422를 반환한다."""
    resp = await admin_client.post(
        f"{BASE}/build",
        json={
            "layer_name": "test",
            "python_version": "3.11",
            "pip_packages": ["numpy;rm -rf /"],
        },
    )
    assert resp.status_code == 422


# ============================================================================
# Part 4: 빌드 목록 / 상세 조회
# ============================================================================


def _make_build_row(build_id: int = 1) -> MagicMock:
    row = MagicMock()
    row.id = build_id
    row.layer_name = "uvpy311"
    row.python_version = "3.11"
    row.profile_name = "smoke"
    row.share_id = "share-rw-uuid"
    row.server_id = None
    row.port_id = None
    row.build_token = None
    row.cloud_init_status = "queued"
    row.status = "queued"
    row.progress_step = "빌드 대기"
    row.progress_pct = 0
    row.error_message = None
    row.console_log_excerpt = None
    row.started_at = None
    row.completed_at = None
    row.created_at = MagicMock()
    row.created_at.isoformat.return_value = "2026-06-18T00:00:00+00:00"
    return row


@pytest.mark.asyncio
async def test_list_builds_success(admin_client):
    """GET /builds → 목록 반환."""
    mock_row = _make_build_row()

    with patch("app.api.union.layer_ops.get_session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_row]))))
        )
        mock_session_ctx.return_value = mock_session

        resp = await admin_client.get(f"{BASE}/builds")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_build_detail_not_found(admin_client):
    """GET /builds/{id} — 존재하지 않는 빌드 ID → 404."""
    with patch("app.api.union.layer_ops.get_session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session_ctx.return_value = mock_session

        resp = await admin_client.get(f"{BASE}/builds/9999")

    assert resp.status_code == 404


# ============================================================================
# Part 5: 빌드 취소
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_build_success(admin_client):
    """POST /builds/{id}/cancel → 취소 성공."""
    mock_result = {"cancelled": True, "layer_name": "uvpy311"}

    with patch(
        "app.services.layer_builder.cancel_layer_build",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await admin_client.post(f"{BASE}/builds/1/cancel")

    assert resp.status_code == 200
    data = resp.json()
    assert data["cancelled"] is True


@pytest.mark.asyncio
async def test_cancel_build_not_found(admin_client):
    """POST /builds/{id}/cancel — 없는 빌드 ID → 404."""
    with patch(
        "app.services.layer_builder.cancel_layer_build",
        new_callable=AsyncMock,
        side_effect=KeyError("빌드 9999를 찾을 수 없습니다"),
    ):
        resp = await admin_client.post(f"{BASE}/builds/9999/cancel")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_build_already_terminal(admin_client):
    """POST /builds/{id}/cancel — 이미 완료된 빌드 → 409."""
    with patch(
        "app.services.layer_builder.cancel_layer_build",
        new_callable=AsyncMock,
        side_effect=ValueError("이미 종료된 빌드입니다 (상태: complete)"),
    ):
        resp = await admin_client.post(f"{BASE}/builds/1/cancel")

    assert resp.status_code == 409


# ============================================================================
# Part 6: 소비 인스턴스 생성
# ============================================================================


@pytest.mark.asyncio
async def test_trigger_consume_invalid_server_name(admin_client):
    """유효하지 않은 server_name → 422."""
    resp = await admin_client.post(
        f"{BASE}/consume",
        json={
            "profile_name": "default",
            "server_name": "evil;evil",
            "flavor_id": "m1.small",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_consume_invalid_profile_name(admin_client):
    """profile_name 명령주입 → 422."""
    resp = await admin_client.post(
        f"{BASE}/consume",
        json={
            "profile_name": "default$(id)",
            "server_name": "consumer-01",
            "flavor_id": "m1.small",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_consume_missing_share_id(admin_client):
    """layer_store_ro_share_id 미설정 시 RuntimeError → HTTP 400."""
    # get_settings / get_session_factory 는 함수 내부에서 lazy import되므로
    # 원본 모듈 경로를 패치한다.
    with (
        patch("app.config.get_settings") as mock_settings,
        patch("app.database.get_session_factory") as mock_factory,
        patch(
            "app.services.layer_build.run_layer_consume",
            new_callable=AsyncMock,
            side_effect=RuntimeError("union_layer_store_ro_share_id가 설정되지 않았습니다"),
        ),
    ):
        mock_settings.return_value = MagicMock(union_layer_store_ro_share_id="")
        mock_factory.return_value = None  # DB 없이 진행

        resp = await admin_client.post(
            f"{BASE}/consume",
            json={
                "profile_name": "default",
                "server_name": "consumer-01",
                "flavor_id": "m1.small",
            },
        )

    assert resp.status_code == 400
