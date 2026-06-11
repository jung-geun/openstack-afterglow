"""mock 단위 테스트: run_ephemeral_build existing_share_id 분기 검증.

라이브 OpenStack 없이 CI에서 실행 가능 — 새 코드 경로를 커버한다.

run_ephemeral_build는 내부 except 블록이 모든 예외를 처리하고 정상 반환하므로
pytest.raises가 아닌 mock 호출 내역(call_args_list)으로 분기를 검증한다.

실행:
  cd backend
  uv run pytest tests/test_existing_share_build.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_settings():
    """config.toml 독립적으로 테스트를 실행하기 위한 최소 Settings mock."""
    s = MagicMock()
    s.builder_network_id = "test-network-id"
    s.default_network_id = ""
    s.builder_flavor_id = "test-flavor-id"
    s.builder_ssh_key_path = ""
    s.builder_image_id = ""
    return s


@pytest.mark.asyncio
async def test_run_ephemeral_build_existing_share_skips_creation():
    """existing_share_id 지정 시 create_builder_share를 호출하지 않는다.

    기존 share의 guard(get_file_storage) + 메타데이터 갱신(update_share_metadata)이
    이루어지고, 신규 share 생성(create_builder_share)은 스킵된다.
    """
    library_id = "python311"
    build_db_id = 99
    existing_share_id = "share-uuid-existing-1234"

    mock_recipe = MagicMock()
    mock_recipe.share_proto = "NFS"
    mock_recipe.share_size_gb = 20
    mock_recipe.base_image_id = "img-uuid"
    mock_recipe.apt_packages = []
    mock_recipe.commands = []

    with (
        patch(
            "app.services.ephemeral_build.library_recipes.get_recipe",
            new_callable=AsyncMock,
            return_value=mock_recipe,
        ),
        patch("app.services.ephemeral_build.lib_svc.get_by_id", return_value=MagicMock(version="3.11")),
        patch("app.services.ephemeral_build.get_service_project_connection", return_value=MagicMock()),
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build._update_db", new_callable=AsyncMock),
        patch("app.services.ephemeral_build.manila.get_file_storage") as mock_get_share,
        patch("app.services.ephemeral_build.manila.update_share_metadata") as mock_update_meta,
        patch(
            "app.services.ephemeral_build.ephemeral_mount.create_builder_share",
            new_callable=AsyncMock,
        ) as mock_create_share,
        # port 생성에서 RuntimeError → except 블록이 처리하고 함수 정상 종료
        patch(
            "app.services.ephemeral_build.neutron.create_port",
            side_effect=RuntimeError("_TEST_STOP_AT_PORT_"),
        ),
    ):
        mock_get_share.return_value = MagicMock(id=existing_share_id)

        from app.services.ephemeral_build import run_ephemeral_build

        # run_ephemeral_build는 내부에서 모든 예외를 처리하고 정상 반환한다
        await run_ephemeral_build(library_id, build_db_id, existing_share_id=existing_share_id)

        # ── 핵심 검증 ──────────────────────────────────────────────────────

        # 1. create_builder_share는 호출되지 않아야 한다
        mock_create_share.assert_not_called()

        # 2. get_file_storage(conn, existing_share_id) 가드 호출 검증
        mock_get_share.assert_called_once()
        positional = mock_get_share.call_args[0]
        assert positional[1] == existing_share_id, f"get_file_storage가 올바른 share_id로 호출되지 않음: {positional}"

        # 3. update_share_metadata: 첫 번째 호출이 building 메타데이터여야 한다
        # (두 번째 호출은 except 블록의 error 상태 갱신)
        assert mock_update_meta.call_count >= 1
        first_meta_arg = mock_update_meta.call_args_list[0][0][2]
        assert first_meta_arg["union_type"] == "ephemeral-build"
        assert first_meta_arg["union_status"] == "building"
        assert first_meta_arg["union_library"] == library_id
        assert first_meta_arg["union_version"] == "3.11"


@pytest.mark.asyncio
async def test_run_ephemeral_build_existing_share_guard_raises_on_not_found():
    """service conn에서 share를 찾을 수 없을 때 에러 처리 후 빌드를 실패로 기록한다.

    guard 실패 시 create_builder_share는 호출되지 않아야 한다.
    """
    library_id = "python311"
    build_db_id = 100
    missing_share_id = "share-uuid-does-not-exist"

    mock_recipe = MagicMock()
    mock_recipe.share_proto = "NFS"
    mock_recipe.share_size_gb = 20
    mock_recipe.base_image_id = "img-uuid"
    mock_recipe.apt_packages = []
    mock_recipe.commands = []

    with (
        patch(
            "app.services.ephemeral_build.library_recipes.get_recipe",
            new_callable=AsyncMock,
            return_value=mock_recipe,
        ),
        patch("app.services.ephemeral_build.lib_svc.get_by_id", return_value=MagicMock(version="3.11")),
        patch("app.services.ephemeral_build.get_service_project_connection", return_value=MagicMock()),
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build._update_db", new_callable=AsyncMock),
        # share 조회 실패 시뮬레이션
        patch(
            "app.services.ephemeral_build.manila.get_file_storage",
            side_effect=Exception("ResourceNotFound"),
        ),
        patch(
            "app.services.ephemeral_build.ephemeral_mount.create_builder_share",
            new_callable=AsyncMock,
        ) as mock_create_share,
    ):
        from app.services.ephemeral_build import run_ephemeral_build

        # guard 실패 → 외부 except가 처리 → 함수 정상 반환
        await run_ephemeral_build(library_id, build_db_id, existing_share_id=missing_share_id)

        # guard 실패 시 create_builder_share는 호출되지 않아야 한다
        mock_create_share.assert_not_called()


@pytest.mark.asyncio
async def test_run_ephemeral_build_no_existing_share_creates_new():
    """existing_share_id 미지정(기본 경로) 시 create_builder_share를 호출한다."""
    library_id = "python311"
    build_db_id = 101
    new_share_id = "share-uuid-newly-created"

    mock_recipe = MagicMock()
    mock_recipe.share_proto = "NFS"
    mock_recipe.share_size_gb = 20
    mock_recipe.base_image_id = "img-uuid"
    mock_recipe.apt_packages = []
    mock_recipe.commands = []

    with (
        patch(
            "app.services.ephemeral_build.library_recipes.get_recipe",
            new_callable=AsyncMock,
            return_value=mock_recipe,
        ),
        patch("app.services.ephemeral_build.lib_svc.get_by_id", return_value=MagicMock(version="3.11")),
        patch("app.services.ephemeral_build.get_service_project_connection", return_value=MagicMock()),
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build._update_db", new_callable=AsyncMock),
        patch("app.services.ephemeral_build.manila.get_file_storage") as mock_get_share,
        patch(
            "app.services.ephemeral_build.ephemeral_mount.create_builder_share",
            new_callable=AsyncMock,
            return_value=new_share_id,
        ) as mock_create_share,
        # port 생성에서 중단 — 이후 로직은 검증 범위 밖
        patch(
            "app.services.ephemeral_build.neutron.create_port",
            side_effect=RuntimeError("_TEST_STOP_AT_PORT_"),
        ),
    ):
        from app.services.ephemeral_build import run_ephemeral_build

        # run_ephemeral_build는 내부에서 모든 예외를 처리하고 정상 반환한다
        await run_ephemeral_build(library_id, build_db_id)  # existing_share_id 없음

        # 기본 경로: create_builder_share가 호출되어야 한다
        mock_create_share.assert_called_once()

        # get_file_storage guard는 호출되지 않아야 한다
        mock_get_share.assert_not_called()
