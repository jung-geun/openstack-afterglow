"""notion_worker 워커 동작 + 기본값 30분 + FastAPI-free 회귀 가드 테스트."""

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. 기본값 30분 검증
# ---------------------------------------------------------------------------


def test_notion_target_create_request_default_interval():
    """NotionTargetCreateRequest의 interval_minutes 기본값이 30이어야 한다."""
    from app.api.identity.admin_notion import NotionTargetCreateRequest

    req = NotionTargetCreateRequest(api_key="k", database_id="d")
    assert req.interval_minutes == 30


def test_notion_config_request_default_interval():
    """NotionConfigRequest의 interval_minutes 기본값이 30이어야 한다."""
    from app.api.identity.admin_notion import NotionConfigRequest

    req = NotionConfigRequest(api_key="k", database_id="d")
    assert req.interval_minutes == 30


# ---------------------------------------------------------------------------
# 2. 워커 사이클이 interval_minutes를 존중하는지 검증
# ---------------------------------------------------------------------------


@pytest.fixture
def make_target():
    """테스트용 NotionTarget dict 생성 헬퍼."""

    def _make(
        target_id: int = 1,
        enabled: bool = True,
        interval_minutes: int = 30,
        last_sync: str | None = None,
    ) -> dict:
        return {
            "id": target_id,
            "enabled": enabled,
            "interval_minutes": interval_minutes,
            "last_sync": last_sync,
            "api_key": "test-api-key",
            "database_id": "test-db-id",
            "users_database_id": "",
            "hypervisors_database_id": "",
            "gpu_spec_database_id": "",
        }

    return _make


@pytest.mark.asyncio
async def test_worker_cycle_skips_disabled_target(make_target):
    """enabled=False 타겟은 동기화를 건너뛴다."""
    from app.notion_worker import _run_sync_cycle

    target = make_target(enabled=False)

    with (
        patch("app.notion_worker._run_notion_target_sync", new_callable=AsyncMock) as mock_sync,
        patch("app.services.notion_sync.list_notion_targets", new_callable=AsyncMock, return_value=[target]),
        patch("app.services.notion_sync.get_notion_config", new_callable=AsyncMock, return_value=None),
    ):
        await _run_sync_cycle()

    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_worker_cycle_skips_target_within_interval(make_target):
    """마지막 동기화 경과 시간이 interval_minutes 미만이면 건너뛴다."""
    from app.notion_worker import _run_sync_cycle

    # 방금 동기화됨 (5분 전) — 30분 간격이므로 아직 스킵
    recent = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    target = make_target(interval_minutes=30, last_sync=recent)

    with (
        patch("app.notion_worker._run_notion_target_sync", new_callable=AsyncMock) as mock_sync,
        patch("app.services.notion_sync.list_notion_targets", new_callable=AsyncMock, return_value=[target]),
        patch("app.services.notion_sync.get_notion_config", new_callable=AsyncMock, return_value=None),
    ):
        await _run_sync_cycle()

    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_worker_cycle_syncs_target_after_interval(make_target):
    """마지막 동기화 경과 시간이 interval_minutes 이상이면 동기화한다."""
    from app.notion_worker import _run_sync_cycle

    # 45분 전 동기화 — 30분 간격이므로 실행해야 함
    old = (datetime.now(UTC) - timedelta(minutes=45)).isoformat()
    target = make_target(interval_minutes=30, last_sync=old)

    with (
        patch("app.notion_worker._run_notion_target_sync", new_callable=AsyncMock) as mock_sync,
        patch("app.services.notion_sync.list_notion_targets", new_callable=AsyncMock, return_value=[target]),
        patch("app.services.notion_sync.get_notion_config", new_callable=AsyncMock, return_value=None),
    ):
        await _run_sync_cycle()

    mock_sync.assert_called_once_with(target)


@pytest.mark.asyncio
async def test_worker_cycle_syncs_target_with_no_last_sync(make_target):
    """last_sync가 None(한 번도 동기화 안 됨)이면 즉시 동기화한다."""
    from app.notion_worker import _run_sync_cycle

    target = make_target(last_sync=None)

    with (
        patch("app.notion_worker._run_notion_target_sync", new_callable=AsyncMock) as mock_sync,
        patch("app.services.notion_sync.list_notion_targets", new_callable=AsyncMock, return_value=[target]),
        patch("app.services.notion_sync.get_notion_config", new_callable=AsyncMock, return_value=None),
    ):
        await _run_sync_cycle()

    mock_sync.assert_called_once_with(target)


@pytest.mark.asyncio
async def test_worker_cycle_respects_custom_interval(make_target):
    """interval_minutes가 5분으로 설정된 타겟은 5분이 지나면 동기화한다."""
    from app.notion_worker import _run_sync_cycle

    # 6분 전 동기화 — 5분 간격이므로 실행해야 함
    old = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()
    target = make_target(interval_minutes=5, last_sync=old)

    with (
        patch("app.notion_worker._run_notion_target_sync", new_callable=AsyncMock) as mock_sync,
        patch("app.services.notion_sync.list_notion_targets", new_callable=AsyncMock, return_value=[target]),
        patch("app.services.notion_sync.get_notion_config", new_callable=AsyncMock, return_value=None),
    ):
        await _run_sync_cycle()

    mock_sync.assert_called_once_with(target)


# ---------------------------------------------------------------------------
# 3. FastAPI-free 회귀 가드
#    서브프로세스로 격리 실행해 fastapi/starlette가 워커 import 경로에
#    끌려들어오지 않음을 확인한다. Phase 2 리팩토링의 핵심 보장.
# ---------------------------------------------------------------------------

_FASTAPI_FREE_SCRIPT = """
import sys

# 워커 진입점 모듈
import app.worker
import app.notion_worker

# 런타임에 실제 사용되는 서비스 모듈 (지연 import를 해당 경로로 강제 적재)
import app.services.gpu_inventory
import app.services.openstack_inventory
import app.services.notion_sync
import app.services.k3s_health
import app.services.k3s_stampede

leaked = [m for m in sys.modules if m in ("fastapi", "starlette", "uvicorn")]
if leaked:
    print("FAIL: leaked modules:", leaked, file=sys.stderr)
    sys.exit(1)
print("OK")
"""

# 테스트 파일 기준 backend/ 루트 경로 (CI/CD 환경 호환)
_BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_worker_imports_are_fastapi_free():
    """app.worker 및 app.notion_worker import 시 fastapi/starlette/uvicorn가
    sys.modules에 없어야 한다 (경량 이미지 보장).
    서비스 레이어 모듈(notion_sync, k3s_health 등)도 함께 검사해 지연 import 경로 포함.
    """
    result = subprocess.run(
        [sys.executable, "-c", _FASTAPI_FREE_SCRIPT],
        capture_output=True,
        text=True,
        cwd=str(_BACKEND_DIR),
    )
    assert result.returncode == 0, (
        f"워커 import 경로에 FastAPI/starlette/uvicorn가 포함됨:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert result.stdout.strip() == "OK"
