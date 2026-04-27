"""
라이브러리 파일 스토리지 자동 빌드 서비스.

Manila CephFS share 생성 → CephX access rule → 임시 VM(cloud-init) 자동 생성
→ VM 내부에서 패키지 설치 → VM SHUTOFF 감지 → 메타데이터 업데이트 → VM 삭제
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from app.config import get_settings
from app.services import libraries as lib_svc
from app.services import manila

_logger = logging.getLogger(__name__)

# 빌드 중인 작업 추적 {library_id: {share_id, server_id, status}} (인메모리 캐시, DB가 원본)
_active_builds: dict[str, dict] = {}


async def _update_build_db(
    build_id: int,
    *,
    status: str | None = None,
    progress_step: str | None = None,
    progress_pct: int | None = None,
    server_id: str | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> None:
    """DB의 library_builds 행을 업데이트한다."""
    from app.database import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return
    from app.models.db import LibraryBuild

    async with factory() as session:
        from sqlalchemy import select

        row = (await session.execute(select(LibraryBuild).where(LibraryBuild.id == build_id))).scalar_one_or_none()
        if row is None:
            return
        if status is not None:
            row.status = status
        if progress_step is not None:
            row.progress_step = progress_step
        if progress_pct is not None:
            row.progress_pct = progress_pct
        if server_id is not None:
            row.server_id = server_id
        if error_message is not None:
            row.error_message = error_message
        if completed:
            row.completed_at = datetime.now(UTC)
        await session.commit()


# 설치 스크립트 템플릿 (라이브러리별)
_INSTALL_SCRIPTS: dict[str, str] = {
    "python311": """
apt-get update -qq
apt-get install -y python3.11 python3.11-venv python3-pip
mkdir -p /mnt/share/usr_local
cp -a /usr/local/. /mnt/share/usr_local/
""",
    "torch": """
pip3 install --no-cache-dir --target=/mnt/share/usr_local/lib/python3/dist-packages \
    torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0
""",
    "vllm": """
pip3 install --no-cache-dir --target=/mnt/share/usr_local/lib/python3/dist-packages \
    vllm==0.6.0
""",
    "jupyter": """
pip3 install --no-cache-dir --target=/mnt/share/usr_local/lib/python3/dist-packages \
    jupyterlab==4.2.0 ipykernel
""",
}


def _generate_cloudinit(
    ceph_monitors: str,
    share_path: str,
    cephx_user: str,
    cephx_secret: str,
    library_id: str,
) -> str:
    """빌더 VM용 cloud-init 스크립트 생성."""
    install_script = _INSTALL_SCRIPTS.get(library_id, "echo 'Unknown library'")

    return f"""#!/bin/bash
set -e
exec > /var/log/union-builder.log 2>&1

# 오류 발생 시 에러 마커 작성 후 종료
_on_error() {{
    echo "[union-builder] BUILD FAILED at line $1"
    sync 2>/dev/null || true
    umount /mnt/share 2>/dev/null || true
    poweroff
}}
trap '_on_error $LINENO' ERR

echo "[union-builder] Starting library build: {library_id}"

# CephFS 마운트를 위한 패키지 설치
apt-get update -qq
apt-get install -y ceph-common python3-pip

# CephFS 마운트
mkdir -p /mnt/share
echo "{cephx_secret}" > /tmp/ceph.secret
mount -t ceph {ceph_monitors}:{share_path} /mnt/share -o name={cephx_user},secretfile=/tmp/ceph.secret
rm -f /tmp/ceph.secret

echo "[union-builder] CephFS mounted, starting package installation"

# 패키지 설치
{install_script}

# 완료 마커 파일 작성
echo '{{"status": "ready", "built_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'", "library": "{library_id}"}}' > /mnt/share/.union_build_complete

# 동기화 및 언마운트
sync
umount /mnt/share

echo "[union-builder] Build complete, shutting down"
poweroff
"""


def get_active_builds() -> dict[str, dict]:
    """현재 진행 중인 빌드 목록 반환."""
    return dict(_active_builds)


async def start_build(
    conn: openstack.connection.Connection,
    library_id: str,
) -> dict:
    """라이브러리 파일 스토리지 자동 빌드 시작.

    Returns: {file_storage_id, server_id, status}
    """
    settings = get_settings()

    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")

    lib = lib_svc.get_by_id(library_id)

    # 빌더 설정 확인
    image_id = settings.builder_image_id
    flavor_id = settings.builder_flavor_id
    network_id = settings.builder_network_id or settings.default_network_id
    if not image_id or not flavor_id:
        raise RuntimeError("빌더 VM 설정이 없습니다 (config.toml [builder] image_id, flavor_id 필요)")

    # 1. Manila share 생성
    _logger.info("[builder] Manila share 생성 시작: %s", library_id)
    file_storage = await asyncio.to_thread(
        manila.create_file_storage,
        conn,
        name=f"union-prebuilt-{library_id}",
        size_gb=_get_lib_size(library_id),
        share_network_id=settings.os_manila_share_network_id,
        share_type=settings.os_manila_share_type,
        metadata={
            "union_type": "prebuilt",
            "union_library": library_id,
            "union_version": lib.version,
            "union_status": "building",
        },
    )
    share_id = file_storage.id
    _logger.info("[builder] Share 생성 완료: %s", share_id)

    # 2. CephX access rule 생성
    cephx_user = f"union-builder-{library_id}"
    access_rule = await asyncio.to_thread(
        manila.create_access_rule,
        conn,
        share_id,
        cephx_user,
        "rw",
        "cephx",
    )
    cephx_secret = access_rule["access_key"]
    _logger.info("[builder] CephX access rule 생성: user=%s", cephx_user)

    # 3. Export location 조회
    export_locations = await asyncio.to_thread(
        manila.get_export_locations,
        conn,
        share_id,
    )
    if not export_locations:
        raise RuntimeError(f"Share {share_id}의 export location을 찾을 수 없습니다")
    # CephFS export path: "mon1,mon2,mon3:/volumes/_nogroup/xxx"
    # 모니터 주소와 경로를 분리
    export_path = export_locations[0]
    if ":" in export_path:
        ceph_mons, share_path = export_path.rsplit(":", 1)
    else:
        ceph_mons = settings.ceph_monitors
        share_path = export_path

    # 4. cloud-init 스크립트 생성
    userdata = _generate_cloudinit(
        ceph_monitors=ceph_mons,
        share_path=share_path,
        cephx_user=cephx_user,
        cephx_secret=cephx_secret,
        library_id=library_id,
    )
    userdata_b64 = base64.b64encode(userdata.encode()).decode()

    # 5. 임시 VM 생성 (이미지에서 직접 부팅)
    _logger.info("[builder] 빌더 VM 생성 시작")
    server = await asyncio.to_thread(
        _create_builder_vm,
        conn,
        library_id,
        image_id,
        flavor_id,
        network_id,
        userdata_b64,
    )
    server_id = server.id
    _logger.info("[builder] 빌더 VM 생성 완료: %s", server_id)

    # DB에 빌드 레코드 생성
    build_db_id: int | None = None
    try:
        from app.database import get_session_factory
        from app.models.db import LibraryBuild

        factory = get_session_factory()
        if factory:
            async with factory() as session:
                build_row = LibraryBuild(
                    library_id=library_id,
                    file_storage_id=share_id,
                    server_id=server_id,
                    status="building",
                    progress_step="VM 생성 완료, 패키지 설치 중",
                    progress_pct=40,
                )
                session.add(build_row)
                await session.commit()
                await session.refresh(build_row)
                build_db_id = build_row.id
    except Exception:
        _logger.warning("[builder] DB 빌드 레코드 생성 실패", exc_info=True)

    # 인메모리 캐시 (호환성 유지)
    build_info = {
        "library_id": library_id,
        "file_storage_id": share_id,
        "server_id": server_id,
        "cephx_user": cephx_user,
        "status": "building",
        "started_at": datetime.now(UTC).isoformat(),
        "build_db_id": build_db_id,
    }
    _active_builds[library_id] = build_info

    # 6. 백그라운드 모니터링 시작
    asyncio.create_task(_monitor_build(conn, library_id, share_id, server_id, build_db_id))

    return {
        "file_storage_id": share_id,
        "server_id": server_id,
        "status": "building",
        "library": library_id,
    }


def _get_lib_size(library_id: str) -> int:
    """라이브러리별 적정 share 크기 (GB)."""
    sizes = {"python311": 5, "torch": 20, "vllm": 15, "jupyter": 5}
    return sizes.get(library_id, 20)


def _create_builder_vm(
    conn: openstack.connection.Connection,
    library_id: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
    userdata_b64: str,
) -> object:
    """이미지에서 직접 부팅하는 임시 VM 생성."""
    server = conn.compute.create_server(
        name=f"union-builder-{library_id}",
        image_id=image_id,
        flavor_id=flavor_id,
        networks=[{"uuid": network_id}],
        user_data=userdata_b64,
        metadata={"union_type": "builder", "union_library": library_id},
    )
    # ACTIVE 상태까지 대기 (최대 10분)
    server = conn.compute.wait_for_server(server, status="ACTIVE", wait=600)
    return server


async def _monitor_build(
    conn: openstack.connection.Connection,
    library_id: str,
    share_id: str,
    server_id: str,
    build_db_id: int | None = None,
):
    """빌더 VM 상태를 모니터링하고 완료 시 정리."""
    _logger.info("[builder] 모니터링 시작: library=%s, server=%s", library_id, server_id)
    try:
        # 최대 30분 대기
        for _ in range(180):
            await asyncio.sleep(10)
            try:
                server = await asyncio.to_thread(conn.compute.get_server, server_id)
                status = server.status
            except Exception:
                _logger.warning("[builder] VM 상태 조회 실패: %s", server_id, exc_info=True)
                continue

            if status == "SHUTOFF":
                _logger.info("[builder] 빌더 VM SHUTOFF 감지: %s", library_id)

                # 빌드 성공 여부 콘솔 로그로 검증
                build_success = False
                try:
                    console_output = await asyncio.to_thread(
                        conn.compute.get_server_console_output, server_id, length=200
                    )
                    log_text = ""
                    if isinstance(console_output, dict):
                        log_text = console_output.get("output", "")
                    elif isinstance(console_output, str):
                        log_text = console_output
                    build_success = "[union-builder] Build complete" in log_text
                    if not build_success:
                        _logger.warning("[builder] 완료 마커 없음 — 빌드 실패로 처리: %s", library_id)
                except Exception:
                    _logger.warning("[builder] 콘솔 로그 조회 실패, 성공으로 간주: %s", library_id, exc_info=True)
                    build_success = True

                if not build_success:
                    await asyncio.to_thread(
                        manila.update_share_metadata,
                        conn,
                        share_id,
                        {"union_status": "error"},
                    )
                    if build_db_id:
                        await _update_build_db(
                            build_db_id,
                            status="error",
                            progress_step="빌드 검증 실패",
                            error_message="콘솔 로그에서 완료 마커를 찾을 수 없음",
                            completed=True,
                        )
                    try:
                        await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
                    except Exception:
                        pass
                    if library_id in _active_builds:
                        _active_builds[library_id]["status"] = "error"
                        del _active_builds[library_id]
                    return

                # CephX access rule 정리 (빌더용)
                try:
                    rules = await asyncio.to_thread(
                        manila.list_access_rules,
                        conn,
                        share_id,
                    )
                    for rule in rules:
                        if rule.get("access_to", "").startswith("union-builder-"):
                            await asyncio.to_thread(
                                manila.revoke_access_rule,
                                conn,
                                share_id,
                                rule["id"],
                            )
                except Exception:
                    _logger.warning("[builder] CephX rule 정리 실패", exc_info=True)

                # 읽기 전용 CephX access rule 생성
                ro_user = f"union-ro-{library_id}"
                try:
                    await asyncio.to_thread(
                        manila.create_access_rule,
                        conn,
                        share_id,
                        ro_user,
                        "ro",
                        "cephx",
                    )
                    _logger.info("[builder] 읽기 전용 CephX rule 생성 완료: user=%s", ro_user)
                except Exception:
                    _logger.warning("[builder] 읽기 전용 rule 생성 실패", exc_info=True)
                    ro_user = ""

                # 메타데이터 업데이트
                metadata: dict[str, str] = {
                    "union_status": "ready",
                    "union_built_at": datetime.now(UTC).isoformat(),
                }
                if ro_user:
                    metadata["union_cephx_user"] = ro_user
                await asyncio.to_thread(
                    manila.update_share_metadata,
                    conn,
                    share_id,
                    metadata,
                )
                # prebuilt share는 모든 프로젝트에서 접근할 수 있도록 공개
                try:
                    await asyncio.to_thread(manila.set_share_public, conn, share_id, True)
                except Exception:
                    _logger.warning(
                        "[builder] set_share_public 실패 (격리 필터에서 노출 불가): %s", share_id, exc_info=True
                    )
                _logger.info("[builder] 빌드 완료 처리: %s", library_id)

                # DB 상태 업데이트
                if build_db_id:
                    await _update_build_db(
                        build_db_id,
                        status="complete",
                        progress_step="빌드 완료",
                        progress_pct=100,
                        completed=True,
                    )

                # VM 삭제
                try:
                    await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
                    _logger.info("[builder] 빌더 VM 삭제 완료: %s", server_id)
                except Exception:
                    _logger.warning("[builder] VM 삭제 실패: %s", server_id, exc_info=True)

                if library_id in _active_builds:
                    _active_builds[library_id]["status"] = "complete"
                    del _active_builds[library_id]
                return

            if status == "ERROR":
                _logger.error("[builder] 빌더 VM ERROR 상태: %s", server_id)
                await asyncio.to_thread(
                    manila.update_share_metadata,
                    conn,
                    share_id,
                    {"union_status": "error"},
                )
                if build_db_id:
                    await _update_build_db(
                        build_db_id,
                        status="error",
                        progress_step="VM 오류 발생",
                        error_message="빌더 VM이 ERROR 상태로 전환됨",
                        completed=True,
                    )
                try:
                    await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
                except Exception:
                    pass
                if library_id in _active_builds:
                    _active_builds[library_id]["status"] = "error"
                    del _active_builds[library_id]
                return

        # 타임아웃
        _logger.error("[builder] 빌드 타임아웃 (30분): %s", library_id)
        await asyncio.to_thread(
            manila.update_share_metadata,
            conn,
            share_id,
            {"union_status": "timeout"},
        )
        if build_db_id:
            await _update_build_db(
                build_db_id,
                status="timeout",
                progress_step="빌드 타임아웃",
                error_message="30분 내 빌드가 완료되지 않음",
                completed=True,
            )
        try:
            await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
        except Exception:
            pass
        if library_id in _active_builds:
            del _active_builds[library_id]

    except Exception:
        _logger.error("[builder] 모니터링 예외: %s", library_id, exc_info=True)
        if build_db_id:
            await _update_build_db(
                build_db_id,
                status="error",
                progress_step="모니터링 예외",
                error_message="모니터링 중 예외 발생",
                completed=True,
            )
        if library_id in _active_builds:
            del _active_builds[library_id]


async def cancel_build(conn: openstack.connection.Connection, build_db_id: int) -> dict:
    """진행 중인 빌드를 취소하고 리소스를 정리한다.

    Returns:
        { "cancelled": True, "library_id": str, "server_deleted": bool }
    """
    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DB가 초기화되지 않았습니다")

    async with factory() as session:
        from sqlalchemy import select

        row = (await session.execute(select(LibraryBuild).where(LibraryBuild.id == build_db_id))).scalar_one_or_none()
        if row is None:
            raise KeyError(f"빌드 {build_db_id}를 찾을 수 없습니다")

        terminal_states = {"complete", "error", "timeout", "cancelled"}
        if row.status in terminal_states:
            raise ValueError(f"이미 종료된 빌드입니다 (상태: {row.status})")

        library_id = row.library_id
        server_id = row.server_id

        # DB 상태 취소로 변경
        row.status = "cancelled"
        row.progress_step = "사용자 취소"
        row.error_message = "관리자에 의해 취소됨"
        row.completed_at = datetime.now(UTC)
        await session.commit()

    # 인메모리 캐시 정리
    if library_id in _active_builds:
        del _active_builds[library_id]

    # VM 삭제 (best-effort)
    server_deleted = False
    if server_id:
        try:
            await asyncio.to_thread(conn.compute.delete_server, server_id, force=True)
            server_deleted = True
            _logger.info("[builder] 취소로 인한 빌더 VM 삭제 완료: %s", server_id)
        except Exception:
            _logger.warning("[builder] 취소 시 VM 삭제 실패: %s", server_id, exc_info=True)

    return {"cancelled": True, "library_id": library_id, "server_deleted": server_deleted}
