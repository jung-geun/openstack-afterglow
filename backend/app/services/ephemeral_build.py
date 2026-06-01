"""ephemeral VM cloud-init 라이브러리 빌드 오케스트레이터.

빌드 요청 → Manila share → Neutron port(IP 예약) → Access rule →
cloud-init user_data 렌더 → Nova server(port attach) →
SHUTOFF 폴링 → console_output sentinel grep → 성공/실패/indeterminate 처리
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid

import httpx
from datetime import UTC, datetime

from app.config import get_settings
from app.services import ephemeral_mount, library_recipes, manila, neutron, nova
from app.services import libraries as lib_svc
from app.services.builder_vm import _ensure_ephemeral_keypair
from app.services.cloud_init_builder import render_user_data
from app.services.keystone import get_service_project_connection

_logger = logging.getLogger(__name__)

_SHUTOFF_POLL_INTERVAL = 15  # 폴링 간격 (초)
_SHUTOFF_MAX_WAIT = 1800  # 최대 대기 30분
_SUCCESS_SENTINEL = "::AFTERGLOW::SUCCESS::"
_FAILURE_SENTINEL = "::AFTERGLOW::FAILURE::"


# ---------------------------------------------------------------------------
# DB 업데이트 헬퍼
# ---------------------------------------------------------------------------


async def _update_db(
    build_id: int,
    *,
    status: str | None = None,
    cloud_init_status: str | None = None,
    progress_step: str | None = None,
    progress_pct: int | None = None,
    server_id: str | None = None,
    port_id: str | None = None,
    file_storage_id: str | None = None,
    build_token: str | None = None,
    error_message: str | None = None,
    console_log_excerpt: str | None = None,
    completed: bool = False,
) -> None:
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        return

    async with factory() as session:
        row = (await session.execute(select(LibraryBuild).where(LibraryBuild.id == build_id))).scalar_one_or_none()
        if row is None:
            return
        terminal = {"complete", "error", "timeout", "cancelled"}
        if row.status in terminal and not completed:
            return

        if status is not None:
            row.status = status
        if cloud_init_status is not None:
            row.cloud_init_status = cloud_init_status
        if progress_step is not None:
            row.progress_step = progress_step
        if progress_pct is not None:
            row.progress_pct = progress_pct
        if server_id is not None:
            row.server_id = server_id
        if port_id is not None:
            row.port_id = port_id
        if file_storage_id is not None:
            row.file_storage_id = file_storage_id
        if build_token is not None:
            row.build_token = build_token
        if error_message is not None:
            row.error_message = error_message
        if console_log_excerpt is not None:
            row.console_log_excerpt = console_log_excerpt
        if completed:
            row.completed_at = datetime.now(UTC)
        await session.commit()


# ---------------------------------------------------------------------------
# SHUTOFF 폴링
# ---------------------------------------------------------------------------


async def _wait_for_shutoff(conn, server_id: str, build_db_id: int, build_token: str) -> None:
    """VM이 SHUTOFF(또는 ERROR) 될 때까지 폴링한다."""
    from app.services import nova

    waited = 0
    while waited < _SHUTOFF_MAX_WAIT:
        await asyncio.sleep(_SHUTOFF_POLL_INTERVAL)
        waited += _SHUTOFF_POLL_INTERVAL

        server = await asyncio.to_thread(conn.compute.get_server, server_id)
        status = (server.status or "").upper()

        if status in ("SHUTOFF", "ERROR"):
            _logger.info("[ephemeral_build] VM %s 상태: %s (elapsed=%ds)", server_id, status, waited)
            return

        if status == "ACTIVE" and waited > 60:
            try:
                partial = await asyncio.to_thread(nova.get_console_output, conn, server_id, 200)
                success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
                failure_tok = f"{_FAILURE_SENTINEL}{build_token}"
                if success_tok in partial or failure_tok in partial:
                    _logger.info("[ephemeral_build] sentinel 조기 감지 — SHUTOFF 대기 계속")
            except Exception:
                pass

        cloud_status = "booting" if waited < 120 else "installing"
        await _update_db(build_db_id, cloud_init_status=cloud_status)

    raise TimeoutError(f"VM {server_id}이 {_SHUTOFF_MAX_WAIT}s 내에 SHUTOFF 되지 않았습니다")


# ---------------------------------------------------------------------------
# 메인 오케스트레이터
# ---------------------------------------------------------------------------


async def run_ephemeral_build(library_id: str, build_db_id: int) -> None:
    """ephemeral VM cloud-init 빌드 메인 함수. 백그라운드 태스크로 실행된다."""
    settings = get_settings()
    conn = await asyncio.to_thread(get_service_project_connection)

    build_token = uuid.uuid4().hex
    await _update_db(build_db_id, build_token=build_token)

    share_id: str | None = None
    port_id: str | None = None
    server_id: str | None = None
    rw_access_id: str | None = None

    try:
        # ── 1. Recipe 로드 ────────────────────────────────────────────────
        await _update_db(build_db_id, cloud_init_status="queued", progress_step="레시피 로드", progress_pct=2)
        recipe = await library_recipes.get_recipe(library_id)
        if recipe is None:
            raise RuntimeError(f"라이브러리 레시피가 없습니다: {library_id}")

        lib = lib_svc.get_by_id(library_id)
        library_version: str = lib.version

        proto = (recipe.share_proto or "NFS").upper()
        image_id = recipe.base_image_id or settings.builder_image_id
        if not image_id:
            raise RuntimeError("빌드 이미지 ID가 설정되지 않았습니다 (config.toml [builder] image_id 필요)")

        # ── 2. Manila share 생성 ──────────────────────────────────────────
        await _update_db(build_db_id, status="creating_share", progress_step="Manila share 생성", progress_pct=5)
        share_id = await ephemeral_mount.create_builder_share(
            conn,
            name=f"union-prebuilt-{library_id}-{build_token[:8]}",
            size_gb=recipe.share_size_gb,
            share_proto=proto,
            metadata={
                "union_library": library_id,
                "union_version": library_version,
            },
        )
        await _update_db(build_db_id, file_storage_id=share_id)

        # ── 3. Neutron port 사전 생성 (IP 예약) ───────────────────────────
        network_id = settings.builder_network_id or settings.default_network_id
        if not network_id:
            raise RuntimeError("빌드 네트워크 ID가 설정되지 않았습니다 (config.toml [builder] network_id 필요)")

        port_info = await asyncio.to_thread(
            neutron.create_port,
            conn,
            network_id,
            f"afterglow-build-{build_token[:8]}",
        )
        port_id = port_info["id"]
        fixed_ip = port_info["fixed_ip"]
        await _update_db(build_db_id, port_id=port_id)
        _logger.info("[ephemeral_build] port 생성: %s (%s)", port_id, fixed_ip)

        # ── 4. Access rule 생성 ───────────────────────────────────────────
        await _update_db(build_db_id, status="creating_access", progress_step="Access rule 생성", progress_pct=10)

        cephx_user: str | None = None
        cephx_secret: str | None = None

        if proto == "NFS":
            rule = await asyncio.to_thread(
                manila.ensure_nfs_access_rule,
                conn,
                share_id,
                fixed_ip,
                "rw",
                root_squash=False,
                sec_flavor="sys",
            )
            rw_access_id = rule["access_id"]
        else:
            cephx_user = f"union-builder-{library_id}-{build_token[:8]}"
            rule = await asyncio.to_thread(
                manila.create_access_rule,
                conn,
                share_id,
                cephx_user,
                "rw",
                "cephx",
            )
            rw_access_id = rule["access_id"]
            cephx_secret = rule["access_key"]

        _logger.info("[ephemeral_build] access rule 생성: %s (proto=%s)", rw_access_id, proto)

        # ── 5. Export location 조회 ───────────────────────────────────────
        export_locations = await asyncio.to_thread(manila.get_export_locations, conn, share_id)
        if not export_locations:
            raise RuntimeError(f"Share {share_id}의 export location이 없습니다")

        export_path = export_locations[0]

        if proto == "NFS":
            mount_spec: dict = {"share_proto": "NFS", "export_path": export_path}
        else:
            if ":" in export_path:
                ceph_mons, ceph_path = export_path.rsplit(":", 1)
            else:
                ceph_mons, ceph_path = export_path, "/"
            mount_spec = {
                "share_proto": "CEPHFS",
                "ceph_mons": ceph_mons,
                "ceph_path": ceph_path,
                "cephx_user": cephx_user,
                "cephx_secret": cephx_secret,
            }

        # ── 6. user_data 렌더 + server 생성 ──────────────────────────────
        await _update_db(build_db_id, status="creating_vm", progress_step="VM 생성", progress_pct=15)

        user_data_str = render_user_data(recipe, mount_spec, build_token)
        user_data_b64 = base64.b64encode(user_data_str.encode()).decode()

        keypair_name = await _ensure_ephemeral_keypair(conn, settings.builder_ssh_key_path)

        vm_name = f"afterglow-build-{library_id}-{build_token[:8]}"
        server = await asyncio.to_thread(
            conn.compute.create_server,
            name=vm_name,
            image_id=image_id,
            flavor_id=settings.builder_flavor_id,
            networks=[{"port": port_id}],
            user_data=user_data_b64,
            key_name=keypair_name,
            metadata={
                "union_type": "ephemeral-build",
                "union_library": library_id,
                "afterglow_managed": "true",
            },
        )
        server_id = server.id
        await _update_db(
            build_db_id,
            server_id=server_id,
            cloud_init_status="booting",
            progress_step="VM 부팅 중",
            progress_pct=20,
        )
        _logger.info("[ephemeral_build] VM 생성: %s (%s)", vm_name, server_id)

        # ── 7. SHUTOFF 폴링 ───────────────────────────────────────────────
        await _update_db(build_db_id, status="building", progress_step="cloud-init 실행 중", progress_pct=25)
        await _wait_for_shutoff(conn, server_id, build_db_id, build_token)

        # ── 8. sentinel 검증 ──────────────────────────────────────────────
        await _update_db(build_db_id, cloud_init_status="finalizing", progress_step="결과 검증", progress_pct=90)

        console = await asyncio.to_thread(nova.get_console_output, conn, server_id, None)
        excerpt = console[-2000:] if len(console) > 2000 else console
        await _update_db(build_db_id, console_log_excerpt=excerpt)

        success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
        failure_tok = f"{_FAILURE_SENTINEL}{build_token}"

        if success_tok in console:
            await _handle_success(conn, library_id, library_version, share_id, proto, build_db_id, rw_access_id)
            rw_access_id = None  # 이미 회수됨
        elif failure_tok in console:
            raise RuntimeError("cloud-init FAILURE sentinel 감지 — console_log_excerpt 참조")
        else:
            _logger.error("[ephemeral_build] sentinel 부재 (indeterminate): library=%s", library_id)
            await _update_db(
                build_db_id,
                status="error",
                cloud_init_status="indeterminate",
                progress_step="sentinel 부재",
                error_message=(
                    "console_output에서 sentinel을 찾을 수 없습니다. VM panic 또는 console buffer 초과 가능성."
                ),
                completed=True,
            )
            if share_id:
                try:
                    await asyncio.to_thread(
                        manila.update_share_metadata, conn, share_id, {"union_status": "indeterminate"}
                    )
                except Exception:
                    pass

    except Exception as exc:
        _logger.error("[ephemeral_build] 빌드 실패: library=%s", library_id, exc_info=True)
        if share_id:
            try:
                await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "error"})
            except Exception:
                pass
        # httpx.HTTPStatusError의 경우 Manila 응답 본문 메시지 (+ 가용 type 목록) 를 표시
        if isinstance(exc, httpx.HTTPStatusError):
            error_text = manila.format_error_message(exc)[:1000]
        else:
            error_text = str(exc)[:1000]
        await _update_db(
            build_db_id,
            status="error",
            cloud_init_status="failure",
            progress_step="빌드 실패",
            error_message=error_text,
            completed=True,
        )

    finally:
        # 항상 server → port 정리
        if server_id:
            try:
                await asyncio.to_thread(conn.compute.delete_server, server_id)
                _logger.info("[ephemeral_build] server 삭제: %s", server_id)
            except Exception:
                _logger.warning("[ephemeral_build] server 삭제 실패: %s", server_id, exc_info=True)

        if port_id:
            try:
                await asyncio.to_thread(neutron.delete_port, conn, port_id)
                _logger.info("[ephemeral_build] port 삭제: %s", port_id)
            except Exception:
                _logger.warning("[ephemeral_build] port 삭제 실패: %s", port_id, exc_info=True)


async def _handle_success(
    conn,
    library_id: str,
    library_version: str,
    share_id: str,
    proto: str,
    build_db_id: int,
    rw_access_id: str | None,
) -> None:
    """빌드 성공 처리: RW rule 회수 → RO rule 생성 → 메타데이터 갱신 → share 공개."""

    # RW access rule 회수
    if rw_access_id:
        try:
            await asyncio.to_thread(manila.revoke_access_rule, conn, share_id, rw_access_id)
            _logger.info("[ephemeral_build] RW access rule 회수: %s", rw_access_id)
        except Exception:
            _logger.warning("[ephemeral_build] RW access rule 회수 실패", exc_info=True)

    # RO CephX rule 생성 (CephFS만)
    ro_user = f"union-ro-{library_id}"
    metadata: dict[str, str] = {
        "union_type": "prebuilt",  # 완료 share를 prebuilt로 승격 → 409 dedup 정상 작동
        "union_status": "ready",
        "union_built_at": datetime.now(UTC).isoformat(),
        "union_library": library_id,
        "union_version": library_version,
    }

    if proto == "CEPHFS":
        try:
            await asyncio.to_thread(manila.create_access_rule, conn, share_id, ro_user, "ro", "cephx")
            metadata["union_cephx_user"] = ro_user
            _logger.info("[ephemeral_build] RO CephX rule 생성: %s", ro_user)
        except Exception:
            _logger.warning("[ephemeral_build] RO CephX rule 생성 실패", exc_info=True)

    # 메타데이터 갱신
    try:
        await asyncio.to_thread(manila.update_share_metadata, conn, share_id, metadata)
    except Exception:
        _logger.warning("[ephemeral_build] 메타데이터 갱신 실패", exc_info=True)

    # share 공개
    try:
        await asyncio.to_thread(manila.set_share_public, conn, share_id, True)
    except Exception:
        _logger.warning("[ephemeral_build] set_share_public 실패", exc_info=True)

    await _update_db(
        build_db_id,
        status="complete",
        cloud_init_status="success",
        progress_step="빌드 완료",
        progress_pct=100,
        completed=True,
    )
    _logger.info("[ephemeral_build] 빌드 성공: library=%s, share=%s", library_id, share_id)


async def cancel_ephemeral_build(build_db_id: int) -> dict:
    """진행 중인 ephemeral 빌드를 취소하고 OpenStack 리소스를 정리한다."""
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

        terminal = {"complete", "error", "timeout", "cancelled"}
        if row.status in terminal:
            raise ValueError(f"이미 종료된 빌드입니다 (상태: {row.status})")

        library_id = row.library_id
        share_id = row.file_storage_id
        server_id = row.server_id
        port_id = row.port_id

        row.status = "cancelled"
        row.cloud_init_status = "failure"
        row.progress_step = "사용자 취소"
        row.error_message = "관리자에 의해 취소됨"
        row.completed_at = datetime.now(UTC)
        await session.commit()

    conn = await asyncio.to_thread(get_service_project_connection)

    # server 삭제
    if server_id:
        try:
            await asyncio.to_thread(conn.compute.delete_server, server_id)
            _logger.info("[ephemeral_build] cancel: server 삭제 %s", server_id)
        except Exception:
            _logger.warning("[ephemeral_build] cancel: server 삭제 실패 %s", server_id, exc_info=True)

    # port 삭제
    if port_id:
        try:
            await asyncio.to_thread(neutron.delete_port, conn, port_id)
            _logger.info("[ephemeral_build] cancel: port 삭제 %s", port_id)
        except Exception:
            _logger.warning("[ephemeral_build] cancel: port 삭제 실패 %s", port_id, exc_info=True)

    # Manila RW access rule 회수 (best-effort)
    if share_id:
        try:
            rules = await asyncio.to_thread(manila.list_access_rules, conn, share_id)
            for rule in rules:
                at = rule.get("access_to", "")
                if at.startswith("union-builder-") or (
                    rule.get("access_type") == "ip" and rule.get("access_level") == "rw"
                ):
                    await asyncio.to_thread(manila.revoke_access_rule, conn, share_id, rule["id"])
            await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "cancelled"})
        except Exception:
            _logger.warning("[ephemeral_build] cancel: access rule 정리 실패", exc_info=True)

    return {"cancelled": True, "library_id": library_id}
