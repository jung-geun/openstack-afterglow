"""squashfs 레이어 빌드 태스크 관리자.

asyncio 백그라운드 태스크로 LayerBuild를 실행하고 진행 상태를 인메모리 캐시한다.
DB가 원본이고 이 캐시는 빠른 조회용이다.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.services.layer_ubuntu import normalize_ubuntu_base


def _base_image_fields(snapshot: dict | None) -> dict:
    if not isinstance(snapshot, dict):
        return {}
    return {
        name: snapshot.get(name)
        for name in (
            "base_image_id",
            "base_image_name",
            "base_image_checksum",
            "base_image_os_hash_algo",
            "base_image_os_hash_value",
            "base_image_min_disk",
            "base_image_visibility",
            "base_image_owner",
            "source_metadata",
        )
        if snapshot.get(name) is not None
    }


_logger = logging.getLogger(__name__)

# 진행 중인 빌드 추적 {build_db_id: info_dict}
_active_builds: dict[int, dict] = {}
# 백그라운드 태스크 참조 (GC 방지)
_background_tasks: set[asyncio.Task] = set()


def get_active_builds() -> list[dict]:
    """현재 진행 중인 레이어 빌드 목록."""
    return list(_active_builds.values())


async def start_layer_build(
    layer_name: str,
    kind: str,
    python_version: str | None,
    pip_packages: list[str],
    apt_packages: list[str] | None = None,
    pip_index_url: str | None = None,
    pip_extra_index_urls: list[str] | None = None,
    pip_find_links: list[str] | None = None,
    parent_artifact_id: int | None = None,
    nvidia_driver_branch: str | None = None,
    ubuntu_base: str | None = None,
    base_image_snapshot: dict | None = None,
    source_metadata: dict | None = None,
) -> dict:
    """LayerBuild DB 레코드를 생성하고 백그라운드 빌드 태스크를 시작한다.

    share_id는 run_layer_build에서 동적 생성 후 DB에 기록한다.
    """
    from app.database import get_session_factory
    from app.models.db import LayerBuild

    if base_image_snapshot and base_image_snapshot.get("ubuntu_base"):
        effective_ubuntu_base = normalize_ubuntu_base(base_image_snapshot.get("ubuntu_base"))
    else:
        effective_ubuntu_base = normalize_ubuntu_base(ubuntu_base)
    if source_metadata is not None:
        base_image_snapshot = {**(base_image_snapshot or {}), "source_metadata": source_metadata}
    build_db_id: int | None = None
    factory = get_session_factory()
    if factory:
        async with factory() as session:
            row = LayerBuild(
                layer_name=layer_name,
                kind=kind,
                python_version=python_version,
                pip_packages=list(pip_packages or []),
                apt_packages=list(apt_packages or []),
                ubuntu_base=effective_ubuntu_base,
                parent_artifact_id=parent_artifact_id,
                share_id="",  # 동적 share — run_layer_build에서 생성 후 갱신
                status="queued",
                cloud_init_status="queued",
                progress_step="빌드 대기",
                progress_pct=0,
                **_base_image_fields(base_image_snapshot),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            build_db_id = row.id
    else:
        _logger.warning("[layer_builder] DB 미가용 — build_db_id 없이 진행")

    if build_db_id is not None:
        _active_builds[build_db_id] = {
            "build_id": build_db_id,
            "layer_name": layer_name,
            "kind": kind,
            "python_version": python_version,
            "parent_artifact_id": parent_artifact_id,
            "pip_packages": list(pip_packages or []),
            "apt_packages": list(apt_packages or []),
            "ubuntu_base": effective_ubuntu_base,
            "pip_index_url": pip_index_url,
            "pip_extra_index_urls": list(pip_extra_index_urls or []),
            "pip_find_links": list(pip_find_links or []),
            "nvidia_driver_branch": nvidia_driver_branch,
            "base_image_id": (base_image_snapshot or {}).get("base_image_id"),
            "base_image_name": (base_image_snapshot or {}).get("base_image_name"),
            "status": "queued",
            "started_at": datetime.now(UTC).isoformat(),
        }

    task = asyncio.create_task(
        _build_task(
            build_db_id=build_db_id,
            layer_name=layer_name,
            kind=kind,
            python_version=python_version,
            pip_packages=pip_packages,
            apt_packages=[] if kind == "nvidia" else apt_packages,
            pip_index_url=pip_index_url,
            pip_extra_index_urls=pip_extra_index_urls,
            pip_find_links=pip_find_links,
            parent_artifact_id=parent_artifact_id,
            nvidia_driver_branch=nvidia_driver_branch,
            ubuntu_base=effective_ubuntu_base,
            base_image_snapshot=base_image_snapshot,
            source_metadata=source_metadata,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "build_id": build_db_id,
        "layer_name": layer_name,
        "parent_artifact_id": parent_artifact_id,
        "status": "queued",
        "ubuntu_base": effective_ubuntu_base,
        "base_image_id": (base_image_snapshot or {}).get("base_image_id"),
        "base_image_name": (base_image_snapshot or {}).get("base_image_name"),
    }


async def _build_task(
    build_db_id: int | None,
    layer_name: str,
    kind: str,
    python_version: str | None,
    pip_packages: list[str],
    apt_packages: list[str] | None = None,
    pip_index_url: str | None = None,
    pip_extra_index_urls: list[str] | None = None,
    pip_find_links: list[str] | None = None,
    parent_artifact_id: int | None = None,
    nvidia_driver_branch: str | None = None,
    ubuntu_base: str | None = None,
    base_image_snapshot: dict | None = None,
    source_metadata: dict | None = None,
) -> None:
    """백그라운드 빌드 래퍼 — 완료 시 _active_builds에서 제거."""
    try:
        from app.services.layer_build import run_layer_build

        await run_layer_build(
            build_db_id,
            layer_name,
            kind,
            python_version,
            pip_packages,
            apt_packages,
            pip_index_url=pip_index_url,
            pip_extra_index_urls=pip_extra_index_urls,
            pip_find_links=pip_find_links,
            parent_artifact_id=parent_artifact_id,
            nvidia_driver_branch=nvidia_driver_branch,
            ubuntu_base=ubuntu_base,
            base_image_snapshot=base_image_snapshot,
            source_metadata=source_metadata,
        )
    except Exception:
        _logger.error("[layer_builder] 빌드 태스크 예외: layer=%s", layer_name, exc_info=True)
    finally:
        if build_db_id is not None:
            _active_builds.pop(build_db_id, None)


async def cancel_layer_build(build_db_id: int) -> dict:
    """진행 중인 레이어 빌드를 취소한다."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LayerBuild
    from app.services import manila, neutron
    from app.services.keystone import get_service_project_connection

    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DB가 초기화되지 않았습니다")

    async with factory() as session:
        row = (await session.execute(select(LayerBuild).where(LayerBuild.id == build_db_id))).scalar_one_or_none()
        if row is None:
            raise KeyError(f"빌드 {build_db_id}를 찾을 수 없습니다")

        terminal = {"complete", "error", "timeout", "cancelled"}
        if row.status in terminal:
            raise ValueError(f"이미 종료된 빌드입니다 (상태: {row.status})")

        server_id = row.server_id
        port_id = row.port_id
        share_id = row.share_id
        layer_name = row.layer_name

        row.status = "cancelled"
        row.cloud_init_status = "failure"
        row.progress_step = "사용자 취소"
        row.error_message = "관리자에 의해 취소됨"
        row.completed_at = datetime.now(UTC)
        await session.commit()

    _active_builds.pop(build_db_id, None)

    conn = await asyncio.to_thread(get_service_project_connection)

    if server_id:
        try:
            await asyncio.to_thread(conn.compute.delete_server, server_id)
        except Exception:
            _logger.warning("[layer_builder] 취소: server 삭제 실패 %s", server_id, exc_info=True)

    if port_id:
        try:
            await asyncio.to_thread(neutron.delete_port, conn, port_id)
        except Exception:
            _logger.warning("[layer_builder] 취소: port 삭제 실패 %s", port_id, exc_info=True)

    # NFS RW rule 정리 (best-effort)
    if share_id:
        try:
            rules = await asyncio.to_thread(manila.list_access_rules, conn, share_id)
            for rule in rules:
                if rule.get("access_type") == "ip" and rule.get("access_level") == "rw":
                    await asyncio.to_thread(manila.revoke_access_rule, conn, share_id, rule["id"])
        except Exception:
            _logger.warning("[layer_builder] 취소: NFS rule 정리 실패", exc_info=True)

    return {"cancelled": True, "layer_name": layer_name}
