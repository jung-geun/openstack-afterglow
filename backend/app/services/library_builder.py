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
from app.services.keystone import get_service_project_connection

_logger = logging.getLogger(__name__)

# 빌드 중인 작업 추적 {library_id: {share_id, server_id, status}} (인메모리 캐시, DB가 원본)
_active_builds: dict[str, dict] = {}

# 빌드 대기 큐 (library_id 문자열)
_build_queue: asyncio.Queue[str] = asyncio.Queue()
# 큐에 있는 library_id 집합 (중복 요청 방지용 빠른 조회)
_queued_libraries: set[str] = set()


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


# 모든 라이브러리에서 공통으로 사용하는 uv 부트스트랩
# uv는 astral.sh에서 제공하는 standalone installer를 사용한다.
_UV_BOOTSTRAP = """\
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
export PATH=/usr/local/bin:$PATH
"""

# 설치 스크립트 템플릿 (라이브러리별)
# share 내부 디렉토리 구조는 FHS를 따른다: usr/local/bin, usr/local/lib/python3.11, ...
# 이렇게 해야 user VM의 overlay merged 뷰에서 PATH/PYTHONPATH가 정상 동작한다.
_INSTALL_SCRIPTS: dict[str, str] = {
    "python311": _UV_BOOTSTRAP
    + """\
# cpython-3.11 standalone 빌드를 share의 usr/local/ 아래에 배포
uv python install cpython-3.11 --install-dir /tmp/py311
PYDIR=$(ls /tmp/py311/ | grep cpython-3.11 | head -1)
mkdir -p /mnt/share/usr/local
cp -a /tmp/py311/"$PYDIR"/. /mnt/share/usr/local/
mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages
""",
    "torch": """\
apt-get update -qq
apt-get install -y python3.11
"""
    + _UV_BOOTSTRAP
    + """\
mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages
uv pip install --python python3.11 --no-cache \
    --target /mnt/share/usr/local/lib/python3.11/site-packages \
    torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0
""",
    "vllm": """\
apt-get update -qq
apt-get install -y python3.11
"""
    + _UV_BOOTSTRAP
    + """\
mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages
uv pip install --python python3.11 --no-cache \
    --target /mnt/share/usr/local/lib/python3.11/site-packages \
    vllm==0.6.0
""",
    "jupyter": """\
apt-get update -qq
apt-get install -y python3.11
"""
    + _UV_BOOTSTRAP
    + """\
mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages
uv pip install --python python3.11 --no-cache \
    --target /mnt/share/usr/local/lib/python3.11/site-packages \
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

# CephFS 마운트 및 uv 설치를 위한 패키지 설치
apt-get update -qq
apt-get install -y ceph-common curl python3-pip

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
    library_id: str,
) -> dict:
    """라이브러리 파일 스토리지 자동 빌드 시작.

    Manila share와 빌더 VM은 service 프로젝트에 생성된다.

    Returns: {file_storage_id, server_id, status}
    """
    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")

    settings = get_settings()
    conn = await asyncio.to_thread(get_service_project_connection)

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

    # 6. 백그라운드 모니터링 시작 (service conn을 task 내부에서 새로 생성해 request-scope 닫힘 문제 해결)
    asyncio.create_task(_monitor_build(library_id, share_id, server_id, build_db_id))

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


def _generate_probe_cloudinit(
    ceph_monitors: str,
    share_path: str,
    cephx_user: str,
    cephx_key: str,
) -> str:
    """마운트 검증용 probe VM cloud-init 스크립트.

    RO로 마운트 후 .union_build_complete 존재를 확인한다.
    성공: [union-probe] VERIFY_OK  실패: [union-probe] VERIFY_FAIL
    """
    return f"""#!/bin/bash
set -euo pipefail
exec > /var/log/union-probe.log 2>&1

apt-get update -qq
apt-get install -y -qq ceph-common

mkdir -p /mnt/probe
echo "{cephx_key}" > /tmp/probe.secret
mount -t ceph {ceph_monitors}:{share_path} /mnt/probe \\
    -o name={cephx_user},secretfile=/tmp/probe.secret,ro || {{
    echo "[union-probe] VERIFY_FAIL: mount error"
    rm -f /tmp/probe.secret; poweroff; exit 1
}}
rm -f /tmp/probe.secret

if [ -f /mnt/probe/.union_build_complete ]; then
    echo "[union-probe] VERIFY_OK"
else
    echo "[union-probe] VERIFY_FAIL: marker not found"
fi

umount /mnt/probe
poweroff
"""


async def _verify_layer_accessible(
    conn: openstack.Connection,
    share_id: str,
    library_id: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
) -> bool:
    """빌드 완료된 레이어 share를 probe VM으로 마운트 검증.

    임시 RO CephX access rule을 생성해 probe VM에 주입, SHUTOFF 후
    console 로그에서 VERIFY_OK/FAIL을 판별한다.
    """
    probe_user = f"union-probe-{library_id}"
    probe_server_id: str | None = None

    try:
        # 1. RO access rule 생성
        rule = await asyncio.to_thread(manila.create_access_rule, conn, share_id, probe_user, "ro", "cephx")
        cephx_key = rule["access_key"]

        # 2. export location 조회
        exports = await asyncio.to_thread(manila.get_export_locations, conn, share_id)
        if not exports:
            _logger.warning("[probe] export location 없음: %s", share_id)
            return False
        export = exports[0]
        if ":" in export:
            ceph_monitors, share_path = export.rsplit(":", 1)
        else:
            ceph_monitors = get_settings().ceph_monitors
            share_path = export

        # 3. probe VM cloud-init 생성 + VM 시작
        script = _generate_probe_cloudinit(ceph_monitors, share_path, probe_user, cephx_key)
        userdata_b64 = base64.b64encode(script.encode()).decode()
        probe_server = await asyncio.to_thread(
            conn.compute.create_server,
            name=f"union-probe-{library_id}",
            image_id=image_id,
            flavor_id=flavor_id,
            networks=[{"uuid": network_id}],
            user_data=userdata_b64,
            metadata={"union_type": "probe", "union_library": library_id},
        )
        probe_server_id = probe_server.id
        _logger.info("[probe] VM 생성: %s", probe_server_id)

        # 4. SHUTOFF 대기 (최대 10분)
        for _ in range(60):
            await asyncio.sleep(10)
            srv = await asyncio.to_thread(conn.compute.get_server, probe_server_id)
            if srv.status == "SHUTOFF":
                break
            if srv.status == "ERROR":
                _logger.warning("[probe] VM ERROR 상태: %s", probe_server_id)
                return False
        else:
            _logger.warning("[probe] 타임아웃: %s", probe_server_id)
            return False

        # 5. console 로그 검사
        console = await asyncio.to_thread(conn.compute.get_server_console_output, probe_server_id, length=100)
        log_text = console.get("output", "") if isinstance(console, dict) else (console or "")
        if "[union-probe] VERIFY_OK" in log_text:
            _logger.info("[probe] 검증 성공: %s", library_id)
            return True
        _logger.warning("[probe] VERIFY_FAIL 감지: %s", library_id)
        return False

    except Exception:
        _logger.warning("[probe] 검증 중 예외: %s", library_id, exc_info=True)
        return False
    finally:
        # probe access rule 정리
        try:
            rules = await asyncio.to_thread(manila.list_access_rules, conn, share_id)
            for r in rules:
                if r.get("access_to") == probe_user:
                    await asyncio.to_thread(manila.revoke_access_rule, conn, share_id, r["id"])
        except Exception:
            pass
        # probe VM 삭제
        if probe_server_id:
            try:
                await asyncio.to_thread(conn.compute.delete_server, probe_server_id, force=True)
            except Exception:
                pass


def _create_builder_vm(
    conn: openstack.connection.Connection,
    library_id: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
    userdata_b64: str,
) -> object:
    """이미지에서 직접 부팅하는 임시 VM 생성 (BUILD 상태로 즉시 반환).

    ACTIVE 대기는 _monitor_build가 폴링으로 처리하므로 여기서 기다리지 않는다.
    요청 핸들러가 VM 부팅(수 분)을 기다리지 않게 해 트리거 타임아웃을 방지한다.
    """
    server = conn.compute.create_server(
        name=f"union-builder-{library_id}",
        image_id=image_id,
        flavor_id=flavor_id,
        networks=[{"uuid": network_id}],
        user_data=userdata_b64,
        metadata={"union_type": "builder", "union_library": library_id},
    )
    return server


async def _monitor_build(
    library_id: str,
    share_id: str,
    server_id: str,
    build_db_id: int | None = None,
):
    """빌더 VM 상태를 모니터링하고 완료 시 정리.

    service 프로젝트 conn을 task 내부에서 새로 생성한다.
    요청 핸들러 응답 후 conn이 닫히는 잠재 버그를 방지한다.
    """
    conn = await asyncio.to_thread(get_service_project_connection)
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

                # 빌드 성공 후 마운트 가능 여부 probe VM으로 검증 (A2)
                settings = get_settings()
                image_id = settings.builder_image_id
                flavor_id = settings.builder_flavor_id
                network_id = settings.builder_network_id or settings.default_network_id
                if image_id and flavor_id:
                    if build_db_id:
                        await _update_build_db(build_db_id, progress_step="마운트 검증 중", progress_pct=80)
                    mount_ok = await _verify_layer_accessible(
                        conn, share_id, library_id, image_id, flavor_id, network_id
                    )
                    if not mount_ok:
                        _logger.error("[builder] 마운트 검증 실패: %s", library_id)
                        await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "error"})
                        if build_db_id:
                            await _update_build_db(
                                build_db_id,
                                status="error",
                                progress_step="마운트 검증 실패",
                                error_message="probe VM이 레이어를 마운트하거나 완료 마커를 찾지 못함",
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


async def cancel_build(build_db_id: int) -> dict:
    """진행 중인 빌드를 취소하고 리소스를 정리한다.

    빌더 VM 삭제는 service 프로젝트 conn으로 수행한다.

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

    # VM 삭제 (best-effort) — service 프로젝트 conn 사용
    server_deleted = False
    if server_id:
        try:
            svc_conn = await asyncio.to_thread(get_service_project_connection)
            await asyncio.to_thread(svc_conn.compute.delete_server, server_id, force=True)
            server_deleted = True
            _logger.info("[builder] 취소로 인한 빌더 VM 삭제 완료: %s", server_id)
        except Exception:
            _logger.warning("[builder] 취소 시 VM 삭제 실패: %s", server_id, exc_info=True)

    return {"cancelled": True, "library_id": library_id, "server_deleted": server_deleted}


# ---------------------------------------------------------------------------
# 빌드 큐 (A3)
# ---------------------------------------------------------------------------


async def queue_build(library_id: str) -> dict:
    """라이브러리 빌드 요청을 큐에 추가한다.

    이미 빌드 중이거나 큐에 대기 중인 동일 라이브러리는 거부된다.
    실제 빌드는 _build_worker()가 큐에서 꺼내 처리한다.

    Returns:
        {"status": "queued", "library_id": ..., "queue_position": int}
    """
    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")
    if library_id in _queued_libraries:
        raise RuntimeError(f"이미 빌드 큐에 있는 라이브러리: {library_id}")

    _queued_libraries.add(library_id)
    await _build_queue.put(library_id)
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


async def _build_worker() -> None:
    """빌드 큐 워커 — 애플리케이션 lifespan 동안 실행되는 무한 루프.

    큐에서 library_id를 꺼내 start_build()를 호출한다.
    start_build() 내부에서 asyncio.create_task(_monitor_build(...))가 생성되므로
    워커는 VM 완료를 기다리지 않고 다음 큐 항목을 즉시 처리할 수 있다.
    같은 library_id의 중복 방지는 _active_builds + _queued_libraries 두 집합이 담당한다.
    """
    _logger.info("[builder] 빌드 큐 워커 시작")
    while True:
        library_id = await _build_queue.get()
        _queued_libraries.discard(library_id)
        try:
            _logger.info("[builder] 큐에서 빌드 시작: %s", library_id)
            await start_build(library_id)
        except Exception:
            _logger.error("[builder] 큐 빌드 실패: %s", library_id, exc_info=True)
        finally:
            _build_queue.task_done()
