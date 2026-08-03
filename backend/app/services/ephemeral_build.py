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
from datetime import UTC, datetime

import httpx

from app.services import ephemeral_mount, library_recipes, manila, neutron, nova
from app.services import libraries as lib_svc
from app.services.cloud_init_builder import render_user_data
from app.services.keystone import get_service_project_connection

_logger = logging.getLogger(__name__)

_SHUTOFF_POLL_INTERVAL = 15  # 폴링 간격 (초)
_SHUTOFF_MAX_WAIT = 3600  # 최대 대기 60분 (NFS 병렬 복사 ~7분 + 여유)
_SUCCESS_SENTINEL = "::AFTERGLOW::SUCCESS::"
_FAILURE_SENTINEL = "::AFTERGLOW::FAILURE::"


# ---------------------------------------------------------------------------
# DB 업데이트 헬퍼
# ---------------------------------------------------------------------------


async def _update_db(
    build_id: int | None,
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

    if build_id is None:
        return
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


async def _wait_for_shutoff(conn, server_id: str, build_db_id: int | None, build_token: str) -> tuple[bool, bool]:
    """VM이 SHUTOFF(또는 ERROR) 될 때까지 폴링한다.

    Returns:
        (early_success, early_failure): ACTIVE 상태에서 sentinel이 감지된 경우 True.
        SHUTOFF 후 console이 없는 환경에서 caller가 fallback으로 사용한다.
    """
    from app.services import nova

    waited = 0
    early_success = False
    early_failure = False
    success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
    failure_tok = f"{_FAILURE_SENTINEL}{build_token}"

    while waited < _SHUTOFF_MAX_WAIT:
        await asyncio.sleep(_SHUTOFF_POLL_INTERVAL)
        waited += _SHUTOFF_POLL_INTERVAL

        server = await asyncio.to_thread(conn.compute.get_server, server_id)
        status = (server.status or "").upper()

        if status in ("SHUTOFF", "ERROR"):
            _logger.info("[ephemeral_build] VM %s 상태: %s (elapsed=%ds)", server_id, status, waited)
            return (early_success, early_failure)

        if status == "ACTIVE" and waited > 60:
            try:
                partial = await asyncio.to_thread(nova.get_console_output, conn, server_id, 200)
                if success_tok in partial:
                    early_success = True
                    _logger.info("[ephemeral_build] sentinel 조기 감지 — SHUTOFF 대기 계속")
                elif failure_tok in partial:
                    early_failure = True
            except Exception:
                pass

        cloud_status = "booting" if waited < 120 else "installing"
        await _update_db(build_db_id, cloud_init_status=cloud_status)

    raise TimeoutError(f"VM {server_id}이 {_SHUTOFF_MAX_WAIT}s 내에 SHUTOFF 되지 않았습니다")


# ---------------------------------------------------------------------------
# 메인 오케스트레이터
# ---------------------------------------------------------------------------


async def run_ephemeral_build(
    library_id: str,
    build_db_id: int | None,
    existing_share_id: str | None = None,
    resource_snapshot: dict | None = None,
) -> None:
    """ephemeral VM cloud-init 빌드 메인 함수. 백그라운드 태스크로 실행된다.

    Args:
        library_id:        빌드할 라이브러리 ID.
        build_db_id:       LibraryBuild DB 레코드 ID.
        existing_share_id: 사전 생성된 Manila share ID. 지정 시 새 share를 생성하지
                           않고 이 share를 빌드 대상으로 사용한다. 빌더는 service
                           프로젝트 conn으로 동작하므로, 이 share가 service conn에서
                           조회 가능해야 한다(service 프로젝트 소유 또는 공개 share).
    """
    resource_snapshot = resource_snapshot or {}
    service_project = resource_snapshot.get("openstack.service_project") or {}
    base_image = resource_snapshot.get("base_image") or {}
    builder_flavor = resource_snapshot.get("builder.flavor") or {}
    builder_network = resource_snapshot.get("builder.network") or {}
    manila_snapshot = resource_snapshot.get("manila") or {}
    if not all(
        (
            service_project.get("id"),
            base_image.get("id"),
            builder_flavor.get("id"),
            builder_network.get("id"),
            manila_snapshot.get("share_type"),
            manila_snapshot.get("share_size_gb"),
        )
    ):
        raise RuntimeError("library build resource snapshot is incomplete")
    from app.services.keystone import get_admin_connection_for_project

    conn = await asyncio.to_thread(get_admin_connection_for_project, service_project["id"])

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

        proto = manila_snapshot["share_proto"]
        image_id = base_image["id"]
        # ── 2. Manila share 생성 or 기존 share 사용 ─────────────────────────
        if existing_share_id:
            # 저수준 경로: 사전 생성된 share를 빌드 대상으로 사용
            await _update_db(build_db_id, status="creating_share", progress_step="기존 share 검증", progress_pct=5)
            try:
                await asyncio.to_thread(manila.get_file_storage, conn, existing_share_id)
            except Exception as exc:
                raise RuntimeError(
                    f"사전 생성 share {existing_share_id}를 service 프로젝트에서 찾을 수 없습니다. "
                    "share가 service 프로젝트 소속이거나 공개(is_public=True) 상태여야 합니다. "
                    f"원인: {exc}"
                ) from exc
            share_id = existing_share_id
            # 빌드 시작 메타데이터 세팅 — _handle_success에서 prebuilt로 승격됨
            await asyncio.to_thread(
                manila.update_share_metadata,
                conn,
                share_id,
                {
                    "union_type": "ephemeral-build",
                    "union_status": "building",
                    "union_library": library_id,
                    "union_version": library_version,
                },
            )
            _logger.info("[ephemeral_build] 기존 share 사용: %s (library=%s)", share_id, library_id)
        else:
            # 기본 경로: 새 share 생성
            await _update_db(build_db_id, status="creating_share", progress_step="Manila share 생성", progress_pct=5)
            share_id = await ephemeral_mount.create_builder_share(
                conn,
                name=f"union-prebuilt-{library_id}-{build_token[:8]}",
                size_gb=manila_snapshot["share_size_gb"],
                share_proto=proto,
                share_type=manila_snapshot["share_type"],
                share_network_id=manila_snapshot.get("share_network_id", ""),
                metadata={
                    "union_library": library_id,
                    "union_version": library_version,
                },
            )
        await _update_db(build_db_id, file_storage_id=share_id)

        network_id = builder_network["id"]

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

        vm_name = f"afterglow-build-{library_id}-{build_token[:8]}"

        server = await asyncio.to_thread(
            conn.compute.create_server,
            name=vm_name,
            image_id=image_id,
            flavor_id=builder_flavor["id"],
            networks=[{"port": port_id}],
            user_data=user_data_b64,
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
        early_success, early_failure = await _wait_for_shutoff(conn, server_id, build_db_id, build_token)

        # ── 8. sentinel 검증 ──────────────────────────────────────────────
        await _update_db(build_db_id, cloud_init_status="finalizing", progress_step="결과 검증", progress_pct=90)

        console = ""
        try:
            console = await asyncio.to_thread(nova.get_console_output, conn, server_id, None)
        except Exception:
            # SHUTOFF VM은 console이 없을 수 있음 (hypervisor 구현 차이)
            # early sentinel을 fallback으로 사용
            _logger.warning(
                "[ephemeral_build] console_output 조회 실패 (SHUTOFF 후 console 없음) — "
                "ACTIVE 중 감지한 sentinel 사용: early_success=%s",
                early_success,
            )
        excerpt = console[-2000:] if len(console) > 2000 else console
        await _update_db(build_db_id, console_log_excerpt=excerpt)

        success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
        failure_tok = f"{_FAILURE_SENTINEL}{build_token}"

        if success_tok in console or early_success:
            await _handle_success(conn, library_id, library_version, share_id, proto, build_db_id, rw_access_id)
            rw_access_id = None  # 이미 회수됨
        elif failure_tok in console or early_failure:
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
        try:
            await asyncio.to_thread(conn.close)
        except Exception:
            _logger.warning("[ephemeral_build] service connection close failed", exc_info=True)


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


async def resume_ephemeral_build(
    build_db_id: int,
    library_id: str,
    library_version: str,
    share_id: str,
    server_id: str,
    port_id: str | None,
    build_token: str,
    proto: str = "NFS",
) -> None:
    """백엔드 재시작으로 중단된 ephemeral 빌드를 재개한다.

    VM이 ACTIVE면 SHUTOFF 폴링을 재시작하고, SHUTOFF면 sentinel 검증만 수행한다.
    VM이 없으면 error 처리 후 반환한다.
    """
    conn = await asyncio.to_thread(get_service_project_connection)

    try:
        server = await asyncio.to_thread(conn.compute.get_server, server_id)
        vm_status = (server.status or "").upper()
    except Exception:
        _logger.warning("[ephemeral_build] 재개: VM 없음 (build_id=%d, server=%s)", build_db_id, server_id)
        await _update_db(
            build_db_id,
            status="error",
            cloud_init_status="failure",
            progress_step="재개 실패: VM 없음",
            error_message="백엔드 재시작 후 빌드 VM을 찾을 수 없습니다",
            completed=True,
        )
        if share_id:
            try:
                await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "error"})
            except Exception:
                pass
        return

    early_success = False
    early_failure = False

    try:
        if vm_status == "ACTIVE":
            await _update_db(
                build_db_id,
                status="building",
                progress_step="cloud-init 실행 중 (재개)",
                progress_pct=25,
            )
            early_success, early_failure = await _wait_for_shutoff(conn, server_id, build_db_id, build_token)
        elif vm_status == "ERROR":
            early_failure = True
        # SHUTOFF: sentinel 검증으로 진행

        await _update_db(
            build_db_id,
            cloud_init_status="finalizing",
            progress_step="결과 검증 (재개)",
            progress_pct=90,
        )

        console = ""
        try:
            console = await asyncio.to_thread(nova.get_console_output, conn, server_id, None)
        except Exception:
            _logger.warning("[ephemeral_build] 재개: console_output 조회 실패 (server=%s)", server_id)

        if console:
            excerpt = console[-2000:] if len(console) > 2000 else console
            await _update_db(build_db_id, console_log_excerpt=excerpt)

        success_tok = f"{_SUCCESS_SENTINEL}{build_token}"
        failure_tok = f"{_FAILURE_SENTINEL}{build_token}"

        if success_tok in console or early_success:
            await _handle_success(conn, library_id, library_version, share_id, proto, build_db_id, None)
        elif failure_tok in console or early_failure:
            raise RuntimeError("cloud-init FAILURE sentinel 감지 (재개)")
        else:
            _logger.warning("[ephemeral_build] 재개: sentinel 부재 (indeterminate): library=%s", library_id)
            await _update_db(
                build_db_id,
                status="error",
                cloud_init_status="indeterminate",
                progress_step="sentinel 부재 (재개)",
                error_message="재개 후 sentinel을 찾을 수 없습니다. VM panic 또는 console buffer 초과 가능성.",
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
        _logger.error("[ephemeral_build] 빌드 재개 실패: library=%s", library_id, exc_info=True)
        if share_id:
            try:
                await asyncio.to_thread(manila.update_share_metadata, conn, share_id, {"union_status": "error"})
            except Exception:
                pass
        await _update_db(
            build_db_id,
            status="error",
            cloud_init_status="failure",
            progress_step="재개 실패",
            error_message=str(exc)[:1000],
            completed=True,
        )

    finally:
        if server_id:
            try:
                await asyncio.to_thread(conn.compute.delete_server, server_id)
                _logger.info("[ephemeral_build] 재개: server 삭제: %s", server_id)
            except Exception:
                _logger.warning("[ephemeral_build] 재개: server 삭제 실패: %s", server_id, exc_info=True)
        if port_id:
            try:
                await asyncio.to_thread(neutron.delete_port, conn, port_id)
                _logger.info("[ephemeral_build] 재개: port 삭제: %s", port_id)
            except Exception:
                _logger.warning("[ephemeral_build] 재개: port 삭제 실패: %s", port_id, exc_info=True)


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
