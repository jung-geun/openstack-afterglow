"""
라이브러리 파일 스토리지 자동 빌드 서비스.

Manila share 생성 → Ephemeral Builder VM cloud-init으로 패키지 설치 → DB 결과 반영
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.services import libraries as lib_svc
from app.services import manila
from app.services.keystone import get_service_project_connection

_logger = logging.getLogger(__name__)

# 빌드 중인 작업 추적 {library_id: {share_id, status, ...}} (인메모리 캐시, DB가 원본)
_active_builds: dict[str, dict] = {}

# 빌드 대기 큐 — (library_id, existing_share_id | None) 튜플
_build_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
# 큐에 있는 library_id 집합 (중복 요청 방지용 빠른 조회)
_queued_libraries: set[str] = set()


def get_active_builds() -> dict[str, dict]:
    """현재 진행 중인 빌드 목록 반환."""
    return dict(_active_builds)


async def cancel_build(build_db_id: int) -> dict:
    """진행 중인 빌드를 취소하고 OpenStack 리소스를 정리한다.

    ephemeral 경로(build_token 존재)는 server + port + access rule 정리.

    Returns:
        { "cancelled": True, "library_id": str }
    """
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DB가 초기화되지 않았습니다")

    async with factory() as session:
        row = (await session.execute(select(LibraryBuild).where(LibraryBuild.id == build_db_id))).scalar_one_or_none()
        if row is None:
            raise KeyError(f"빌드 {build_db_id}를 찾을 수 없습니다")

        terminal_states = {"complete", "error", "timeout", "cancelled"}
        if row.status in terminal_states:
            raise ValueError(f"이미 종료된 빌드입니다 (상태: {row.status})")

        library_id = row.library_id
        share_id = row.file_storage_id
        server_id = row.server_id
        port_id = row.port_id
        is_ephemeral = bool(row.build_token)

        row.status = "cancelled"
        row.cloud_init_status = "failure" if is_ephemeral else row.cloud_init_status
        row.progress_step = "사용자 취소"
        row.error_message = "관리자에 의해 취소됨"
        row.completed_at = datetime.now(UTC)
        await session.commit()

    _active_builds.pop(library_id, None)

    conn = await asyncio.to_thread(get_service_project_connection)

    if is_ephemeral:
        # ephemeral 경로: server → port → access rule 정리
        if server_id:
            try:
                await asyncio.to_thread(conn.compute.delete_server, server_id)
                _logger.info("[builder] 취소 — server 삭제: %s", server_id)
            except Exception:
                _logger.warning("[builder] 취소 — server 삭제 실패: %s", server_id, exc_info=True)
        if port_id:
            try:
                from app.services import neutron as _neutron

                await asyncio.to_thread(_neutron.delete_port, conn, port_id)
                _logger.info("[builder] 취소 — port 삭제: %s", port_id)
            except Exception:
                _logger.warning("[builder] 취소 — port 삭제 실패: %s", port_id, exc_info=True)

    # Manila RW rule 정리 (두 경로 모두 best-effort)
    if share_id:
        try:
            rules = await asyncio.to_thread(manila.list_access_rules, conn, share_id)
            for rule in rules:
                at = rule.get("access_to", "")
                # ephemeral NFS RW (ip/rw) 또는 CephX RW rule 회수
                if at.startswith("union-builder-") or (
                    rule.get("access_type") == "ip" and rule.get("access_level") == "rw"
                ):
                    await asyncio.to_thread(manila.revoke_access_rule, conn, share_id, rule["id"])
            _logger.info("[builder] 취소 — RW rule 정리 완료: share=%s", share_id)
        except Exception:
            _logger.warning("[builder] 취소 — RW rule 정리 실패: share=%s", share_id, exc_info=True)

    return {"cancelled": True, "library_id": library_id}


# ---------------------------------------------------------------------------
# 빌드 큐
# ---------------------------------------------------------------------------


async def start_ephemeral_build(library_id: str, existing_share_id: str | None = None) -> dict:
    """Ephemeral VM cloud-init 경로로 라이브러리 빌드를 시작한다.

    DB 레코드를 생성하고 run_ephemeral_build 백그라운드 태스크를 시작한다.

    Args:
        library_id: 빌드할 라이브러리 ID.
        existing_share_id: 사전 생성된 Manila share ID. 지정 시 빌더가 새 share를
            생성하지 않고 이 share를 사용한다. None이면 기존 경로대로 신규 share 생성.
    """
    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")

    # library_id 유효성 검사 (알 수 없는 ID면 여기서 예외)
    lib_svc.get_by_id(library_id)

    build_db_id: int | None = None
    initial_share_id = existing_share_id or ""
    try:
        from app.database import get_session_factory
        from app.models.db import LibraryBuild

        factory = get_session_factory()
        if factory:
            async with factory() as session:
                build_row = LibraryBuild(
                    library_id=library_id,
                    file_storage_id=initial_share_id,  # 기존 share 있으면 미리 기록
                    status="queued",
                    cloud_init_status="queued",
                    progress_step="빌드 대기",
                    progress_pct=0,
                )
                session.add(build_row)
                await session.commit()
                await session.refresh(build_row)
                build_db_id = build_row.id
    except Exception:
        _logger.warning("[builder] DB 레코드 생성 실패", exc_info=True)

    _active_builds[library_id] = {
        "library_id": library_id,
        "file_storage_id": initial_share_id,
        "status": "queued",
        "started_at": datetime.now(UTC).isoformat(),
        "build_db_id": build_db_id,
    }

    asyncio.create_task(
        _ephemeral_build_task(library_id=library_id, build_db_id=build_db_id, existing_share_id=existing_share_id)
    )

    return {"file_storage_id": initial_share_id, "status": "queued", "library": library_id, "build_id": build_db_id}


async def _ephemeral_build_task(library_id: str, build_db_id: int | None, existing_share_id: str | None = None) -> None:
    """백그라운드 ephemeral 빌드 래퍼 — 완료 시 _active_builds에서 제거한다."""
    try:
        if build_db_id is None:
            _logger.error("[builder] DB ID 없이 ephemeral 빌드 실행 불가: %s", library_id)
            return
        from app.services.ephemeral_build import run_ephemeral_build

        await run_ephemeral_build(library_id, build_db_id, existing_share_id=existing_share_id)
    except Exception:
        _logger.error("[builder] ephemeral 빌드 태스크 예외: %s", library_id, exc_info=True)
    finally:
        _active_builds.pop(library_id, None)


async def queue_build(library_id: str, existing_share_id: str | None = None) -> dict:
    """라이브러리 빌드 요청을 큐에 추가한다.

    이미 빌드 중이거나 큐에 대기 중인 동일 라이브러리는 거부된다.

    Args:
        library_id: 빌드할 라이브러리 ID.
        existing_share_id: 사전 생성된 Manila share ID. None이면 신규 share 생성.

    Returns:
        {"status": "queued", "library_id": ..., "queue_position": int}
    """
    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")
    if library_id in _queued_libraries:
        raise RuntimeError(f"이미 빌드 큐에 있는 라이브러리: {library_id}")

    _queued_libraries.add(library_id)
    await _build_queue.put((library_id, existing_share_id))
    position = _build_queue.qsize()
    _logger.info("[builder] 빌드 큐 추가: %s (대기 위치 %d)", library_id, position)
    return {"status": "queued", "library_id": library_id, "queue_position": position}


def get_build_queue_status() -> dict:
    """빌드 큐 및 진행 중 빌드 상태 반환."""
    return {
        "queued": sorted(_queued_libraries),
        "active": sorted(_active_builds.keys()),
        "queue_size": _build_queue.qsize(),
    }


async def cleanup_stale_builds() -> None:
    """백엔드 재시작 시 비터미널 상태로 남은 고아 빌드를 error 로 마킹한다.

    asyncio.Queue 는 인메모리이므로 재시작하면 진행 중이던 태스크가 사라지지만
    DB row 는 building/queued 등 비터미널 상태로 남는다. 이 함수는 startup 시
    해당 row 들을 error 로 마킹해 UI 에서 영구 멈춤으로 보이지 않도록 한다.
    """
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        return

    _TERMINAL = {"complete", "error", "timeout", "cancelled"}
    now = datetime.now(UTC)

    async with factory() as session:
        rows = (
            (await session.execute(select(LibraryBuild).where(LibraryBuild.status.notin_(_TERMINAL)))).scalars().all()
        )

        if not rows:
            return

        ids = [r.id for r in rows]
        for row in rows:
            row.status = "error"
            row.cloud_init_status = "failure"
            row.progress_step = "백엔드 재시작으로 중단됨"
            row.error_message = "백엔드 프로세스가 재시작되어 빌드가 중단되었습니다"
            row.completed_at = now

        await session.commit()

    _logger.warning("[builder] 고아 빌드 %d건 정리됨: ids=%s", len(ids), ids)


async def _build_worker() -> None:
    """빌드 큐 워커 — 애플리케이션 lifespan 동안 실행되는 무한 루프.

    큐에서 library_id를 꺼내 start_ephemeral_build()를 호출한다.
    start_ephemeral_build() 내부에서 asyncio.create_task(_ephemeral_build_task(...))가 생성되므로
    워커는 빌드 완료를 기다리지 않고 다음 큐 항목을 즉시 처리할 수 있다.
    """
    _logger.info("[builder] 빌드 큐 워커 시작")
    while True:
        library_id, existing_share_id = await _build_queue.get()
        _queued_libraries.discard(library_id)
        try:
            _logger.info("[builder] 큐에서 ephemeral 빌드 시작: %s", library_id)
            await start_ephemeral_build(library_id, existing_share_id=existing_share_id)
        except Exception:
            _logger.error("[builder] 큐 빌드 실패: %s", library_id, exc_info=True)
        finally:
            _build_queue.task_done()
