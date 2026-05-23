"""
라이브러리 파일 스토리지 자동 빌드 서비스.

Manila CephFS share 생성 → CephX access rule → 영구 Builder VM에 SSH 접속
→ 원격 패키지 설치 → 진행률 DB 업데이트 → 메타데이터 갱신
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from datetime import UTC, datetime

from app.config import get_settings
from app.services import libraries as lib_svc
from app.services import manila
from app.services.keystone import get_service_project_connection

_logger = logging.getLogger(__name__)

# 빌드 중인 작업 추적 {library_id: {share_id, status, ...}} (인메모리 캐시, DB가 원본)
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
        if row.status in {"complete", "error", "timeout", "cancelled"}:
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

# UI 전송 ID 'pytorch' → 'torch' 동일 스크립트로 처리
_INSTALL_SCRIPTS["pytorch"] = _INSTALL_SCRIPTS["torch"]

# [progress] N 단계명 라인 파싱
_PROGRESS_RE = re.compile(r"\[progress\]\s+(\d+)\s+(.*)")


def get_active_builds() -> dict[str, dict]:
    """현재 진행 중인 빌드 목록 반환."""
    return dict(_active_builds)


def _get_lib_size(library_id: str) -> int:
    """라이브러리별 적정 share 크기 (GB)."""
    sizes = {"python311": 5, "torch": 20, "pytorch": 20, "vllm": 15, "jupyter": 5}
    return sizes.get(library_id, 20)


def _build_ssh_command(
    ceph_mons: str,
    share_path: str,
    cephx_user: str,
    cephx_secret: str,
    install_script: str,
) -> str:
    """Builder VM에서 실행할 마운트+설치 SSH 명령을 구성한다.

    cephx_secret과 install_script는 base64로 인코딩해 특수문자 문제를 회피한다.
    """
    secret_b64 = base64.b64encode(cephx_secret.encode()).decode()
    install_b64 = base64.b64encode(install_script.encode()).decode()

    return (
        "set -euo pipefail\n"
        "CEPH_SECRET_FILE=$(mktemp /tmp/ceph.XXXXXX)\n"
        f"printf '%s' '{secret_b64}' | base64 -d > \"$CEPH_SECRET_FILE\"\n"
        'chmod 600 "$CEPH_SECRET_FILE"\n'
        "MNT=/mnt/share\n"
        'mkdir -p "$MNT"\n'
        f"mount -t ceph '{ceph_mons}:{share_path}' \"$MNT\" "
        f"-o 'name={cephx_user}',secretfile=\"$CEPH_SECRET_FILE\"\n"
        'rm -f "$CEPH_SECRET_FILE"\n'
        "echo '[progress] 30 CephFS 마운트 완료'\n"
        "INSTALL_SH=$(mktemp /tmp/install.XXXXXX.sh)\n"
        f"printf '%s' '{install_b64}' | base64 -d > \"$INSTALL_SH\"\n"
        'bash "$INSTALL_SH"\n'
        'rm -f "$INSTALL_SH"\n'
        "echo '[progress] 80 패키지 설치 완료'\n"
        'touch "$MNT/.union_build_complete"\n'
        "sync\n"
        'umount "$MNT"\n'
        "echo '[progress] 100 빌드 완료'\n"
    )


async def start_build(library_id: str) -> dict:
    """영구 Builder VM에 SSH로 접속해 라이브러리를 빌드한다.

    Manila share와 CephX rule은 service 프로젝트에 생성된다.
    실제 설치는 _ssh_build_task 백그라운드 태스크가 수행한다.

    Returns: {file_storage_id, status, library}
    """
    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")

    settings = get_settings()
    conn = await asyncio.to_thread(get_service_project_connection)

    lib = lib_svc.get_by_id(library_id)

    install_script = _INSTALL_SCRIPTS.get(library_id)
    if install_script is None:
        raise RuntimeError(f"알 수 없는 라이브러리 ID: {library_id}")

    # 1. Manila share 생성
    _logger.info("[builder] Manila share 생성: %s", library_id)
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

    # 2. CephX RW access rule
    cephx_user = f"union-builder-{library_id}"
    try:
        access_rule = await asyncio.to_thread(
            manila.create_access_rule,
            conn,
            share_id,
            cephx_user,
            "rw",
            "cephx",
        )
    except Exception:
        _logger.error("[builder] CephX rule 생성 실패 — share %s 회수", share_id)
        try:
            await asyncio.to_thread(manila.delete_file_storage, conn, share_id)
        except Exception:
            pass
        raise
    cephx_secret = access_rule["access_key"]
    _logger.info("[builder] CephX RW rule 생성: user=%s", cephx_user)

    # 3. Export location 조회
    export_locations = await asyncio.to_thread(manila.get_export_locations, conn, share_id)
    if not export_locations:
        raise RuntimeError(f"Share {share_id}의 export location을 찾을 수 없습니다")
    export_path = export_locations[0]
    if ":" in export_path:
        ceph_mons, share_path = export_path.rsplit(":", 1)
    else:
        ceph_mons = settings.ceph_monitors
        share_path = export_path

    # 4. DB 빌드 레코드 생성
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
                    status="building",
                    progress_step="Builder VM 연결 중",
                    progress_pct=10,
                )
                session.add(build_row)
                await session.commit()
                await session.refresh(build_row)
                build_db_id = build_row.id
    except Exception:
        _logger.warning("[builder] DB 레코드 생성 실패", exc_info=True)

    _active_builds[library_id] = {
        "library_id": library_id,
        "file_storage_id": share_id,
        "cephx_user": cephx_user,
        "status": "building",
        "started_at": datetime.now(UTC).isoformat(),
        "build_db_id": build_db_id,
    }

    # 5. 백그라운드 SSH 빌드 태스크 시작
    asyncio.create_task(
        _ssh_build_task(
            library_id=library_id,
            share_id=share_id,
            ceph_mons=ceph_mons,
            share_path=share_path,
            cephx_user=cephx_user,
            cephx_secret=cephx_secret,
            install_script=install_script,
            build_db_id=build_db_id,
        )
    )

    return {
        "file_storage_id": share_id,
        "status": "building",
        "library": library_id,
    }


async def _ssh_build_task(
    library_id: str,
    share_id: str,
    ceph_mons: str,
    share_path: str,
    cephx_user: str,
    cephx_secret: str,
    install_script: str,
    build_db_id: int | None,
) -> None:
    """Builder VM에 SSH로 접속해 라이브러리를 설치하고 결과를 DB에 반영한다.

    service 프로젝트 conn을 내부에서 새로 생성해 start_build()의 conn 닫힘 문제를 방지한다.
    """
    from app.services import builder_vm as bvm
    from app.services.ssh_executor import stream_command

    conn = await asyncio.to_thread(get_service_project_connection)

    try:
        settings = get_settings()

        endpoint = await bvm.ensure_builder_vm(conn)
        _logger.info("[builder] Builder VM 접속: host=%s, library=%s", endpoint.host, library_id)

        if build_db_id:
            await _update_build_db(build_db_id, progress_step="Builder VM 연결 완료", progress_pct=20)

        cmd = _build_ssh_command(
            ceph_mons=ceph_mons,
            share_path=share_path,
            cephx_user=cephx_user,
            cephx_secret=cephx_secret,
            install_script=install_script,
        )

        def _make_progress_callback(db_id: int | None, lib_id: str) -> object:
            def callback(line: str) -> None:
                _logger.debug("[builder:%s] %s", lib_id, line)
                m = _PROGRESS_RE.match(line)
                if m and db_id:
                    pct = int(m.group(1))
                    step = m.group(2)
                    asyncio.create_task(_update_build_db(db_id, progress_pct=pct, progress_step=step))

            return callback

        exit_code, stderr = await stream_command(
            host=endpoint.host,
            key_path=endpoint.key_path,
            command=cmd,
            line_callback=_make_progress_callback(build_db_id, library_id),
            username=endpoint.username,
            timeout=settings.builder_build_timeout,
        )

        if exit_code != 0:
            error_msg = (stderr[-2000:] if stderr else "") or f"SSH 명령 실패 (exit_code={exit_code})"
            _logger.error("[builder] 빌드 실패 (exit=%d): %s\n%s", exit_code, library_id, error_msg)
            await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "error"})
            if build_db_id:
                await _update_build_db(
                    build_db_id,
                    status="error",
                    progress_step="빌드 실패",
                    error_message=f"exit_code={exit_code}: {error_msg[-500:]}",
                    completed=True,
                )
            _active_builds.pop(library_id, None)
            return

        # 빌드 성공 처리
        _logger.info("[builder] 빌드 성공: %s", library_id)

        # RW CephX rule 회수
        try:
            rules = await asyncio.to_thread(manila.list_access_rules, conn, share_id)
            for rule in rules:
                if rule.get("access_to") == cephx_user:
                    await asyncio.to_thread(manila.revoke_access_rule, conn, share_id, rule["id"])
        except Exception:
            _logger.warning("[builder] RW CephX rule 회수 실패", exc_info=True)

        # RO CephX rule 생성
        ro_user = f"union-ro-{library_id}"
        try:
            await asyncio.to_thread(manila.create_access_rule, conn, share_id, ro_user, "ro", "cephx")
            _logger.info("[builder] RO CephX rule 생성: user=%s", ro_user)
        except Exception:
            _logger.warning("[builder] RO CephX rule 생성 실패", exc_info=True)
            ro_user = ""

        # 메타데이터 갱신
        metadata: dict[str, str] = {
            "union_status": "ready",
            "union_built_at": datetime.now(UTC).isoformat(),
        }
        if ro_user:
            metadata["union_cephx_user"] = ro_user
        await asyncio.to_thread(manila.update_share_metadata, conn, share_id, metadata)

        # share 공개 (모든 프로젝트에서 접근 가능)
        try:
            await asyncio.to_thread(manila.set_share_public, conn, share_id, True)
        except Exception:
            _logger.warning("[builder] set_share_public 실패", exc_info=True)

        # DB 완료
        if build_db_id:
            await _update_build_db(
                build_db_id,
                status="complete",
                progress_step="빌드 완료",
                progress_pct=100,
                completed=True,
            )

        if library_id in _active_builds:
            _active_builds[library_id]["status"] = "complete"
            del _active_builds[library_id]

    except Exception:
        _logger.error("[builder] SSH 빌드 태스크 예외: %s", library_id, exc_info=True)
        try:
            await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "error"})
        except Exception:
            pass
        if build_db_id:
            await _update_build_db(
                build_db_id,
                status="error",
                progress_step="빌드 예외",
                error_message="빌드 중 예외 발생",
                completed=True,
            )
        _active_builds.pop(library_id, None)


async def cancel_build(build_db_id: int) -> dict:
    """진행 중인 빌드를 취소하고 OpenStack 리소스를 정리한다.

    ephemeral 경로(build_token 존재)는 server + port + access rule 정리.
    레거시 SSH 경로는 Manila RW CephX rule만 회수.

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


async def start_ephemeral_build(library_id: str) -> dict:
    """Ephemeral VM cloud-init 경로로 라이브러리 빌드를 시작한다.

    DB 레코드를 생성하고 run_ephemeral_build 백그라운드 태스크를 시작한다.
    """
    if library_id in _active_builds:
        raise RuntimeError(f"이미 빌드 중인 라이브러리: {library_id}")

    # library_id 유효성 검사 (알 수 없는 ID면 여기서 예외)
    lib_svc.get_by_id(library_id)

    build_db_id: int | None = None
    try:
        from app.database import get_session_factory
        from app.models.db import LibraryBuild

        factory = get_session_factory()
        if factory:
            async with factory() as session:
                build_row = LibraryBuild(
                    library_id=library_id,
                    file_storage_id="",  # run_ephemeral_build에서 share 생성 후 갱신
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
        "file_storage_id": "",
        "status": "queued",
        "started_at": datetime.now(UTC).isoformat(),
        "build_db_id": build_db_id,
    }

    asyncio.create_task(_ephemeral_build_task(library_id=library_id, build_db_id=build_db_id))

    return {"file_storage_id": "", "status": "queued", "library": library_id}


async def _ephemeral_build_task(library_id: str, build_db_id: int | None) -> None:
    """백그라운드 ephemeral 빌드 래퍼 — 완료 시 _active_builds에서 제거한다."""
    try:
        if build_db_id is None:
            _logger.error("[builder] DB ID 없이 ephemeral 빌드 실행 불가: %s", library_id)
            return
        from app.services.ephemeral_build import run_ephemeral_build

        await run_ephemeral_build(library_id, build_db_id)
    except Exception:
        _logger.error("[builder] ephemeral 빌드 태스크 예외: %s", library_id, exc_info=True)
    finally:
        _active_builds.pop(library_id, None)


async def queue_build(library_id: str) -> dict:
    """라이브러리 빌드 요청을 큐에 추가한다.

    이미 빌드 중이거나 큐에 대기 중인 동일 라이브러리는 거부된다.

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

    큐에서 library_id를 꺼내 start_ephemeral_build()를 호출한다.
    start_ephemeral_build() 내부에서 asyncio.create_task(_ephemeral_build_task(...))가 생성되므로
    워커는 빌드 완료를 기다리지 않고 다음 큐 항목을 즉시 처리할 수 있다.
    """
    _logger.info("[builder] 빌드 큐 워커 시작")
    while True:
        library_id = await _build_queue.get()
        _queued_libraries.discard(library_id)
        try:
            _logger.info("[builder] 큐에서 ephemeral 빌드 시작: %s", library_id)
            await start_ephemeral_build(library_id)
        except Exception:
            _logger.error("[builder] 큐 빌드 실패: %s", library_id, exc_info=True)
        finally:
            _build_queue.task_done()
