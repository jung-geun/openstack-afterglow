"""ERROR 인스턴스 자동 진단 및 복구 서비스.

수동 복구 사례(cold migration 실패 → 볼륨 attaching 고착)를 기반으로:
1. analyze_error_instance() — 안전 검사 5종 + 시나리오 판정
2. execute_recovery()       — fail-closed 재검증 후 화이트리스트 액션 순차 실행

보안:
- execute_recovery는 클라이언트 전달 step을 신뢰하지 않고 서버측 재분석(fail-closed).
- 액션은 reset_volume_state / reset_server_state / hard_reboot 3종 화이트리스트만.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from app.services import cinder, nova

logger = logging.getLogger(__name__)

# 볼륨 고착 상태 목록
_STUCK_VOLUME_STATUSES = {"attaching", "detaching", "reserved", "error"}

# 안전하게 복구 가능한 마이그레이션 타입 (live-migration은 소스에 도메인 잔존 위험)
_SAFE_MIGRATION_TYPES = {"migration", "resize", "live-migration"}
_RISKY_MIGRATION_TYPES = {"live-migration"}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _collect_server(conn: openstack.connection.Connection, server_id: str) -> dict | None:
    """서버 정보를 수집한다. 실패 시 None."""
    try:
        srv = conn.compute.get_server(server_id)
        flavor = getattr(srv, "flavor", {}) or {}
        image = getattr(srv, "image", {}) or {}
        fault_raw = getattr(srv, "fault", None)
        fault: dict | None = None
        if isinstance(fault_raw, dict):
            fault = {
                "message": fault_raw.get("message"),
                "code": fault_raw.get("code"),
                "created": fault_raw.get("created"),
            }
        elif fault_raw is not None:
            fault = {"message": str(fault_raw), "code": None, "created": None}

        return {
            "id": srv.id,
            "name": getattr(srv, "name", ""),
            "status": (getattr(srv, "status", "") or "").upper(),
            "task_state": getattr(srv, "task_state", None),
            "vm_state": getattr(srv, "vm_state", None),
            "compute_host": getattr(srv, "compute_host", None),
            "flavor_disk": int(flavor.get("disk", 0) if isinstance(flavor, dict) else getattr(flavor, "disk", 0)),
            "flavor_id": flavor.get("id") if isinstance(flavor, dict) else getattr(flavor, "id", None),
            "image_id": image.get("id") if isinstance(image, dict) else None,
            "fault": fault,
        }
    except Exception as exc:
        logger.warning("서버 정보 수집 실패: %s", exc)
        return None


def _collect_migrations(conn: openstack.connection.Connection, server_id: str) -> list[dict]:
    """마이그레이션 이력을 최신순으로 반환한다. 실패 시 빈 목록."""
    try:
        migs = list(conn.compute.migrations(instance_uuid=server_id))
        migs.sort(key=lambda x: getattr(x, "created_at", "") or "", reverse=True)
        result = []
        for m in migs:
            result.append(
                {
                    "id": getattr(m, "id", None),
                    "status": (getattr(m, "status", "") or "").lower(),
                    "migration_type": (getattr(m, "migration_type", "") or "").lower(),
                    "source_compute": getattr(m, "source_compute", None),
                    "dest_compute": getattr(m, "dest_compute", None),
                    "created_at": getattr(m, "created_at", None),
                }
            )
        return result
    except Exception as exc:
        logger.warning("마이그레이션 이력 수집 실패: %s", exc)
        return []


def _collect_active_migrations(conn: openstack.connection.Connection, server_id: str) -> list[dict]:
    """진행 중인 서버 마이그레이션을 반환한다 (MV 2.23+). 실패 시 빈 목록."""
    try:
        active = list(conn.compute.server_migrations(server_id))
        return [
            {
                "id": getattr(m, "id", None),
                "status": getattr(m, "status", None),
                "migration_type": getattr(m, "migration_type", None),
            }
            for m in active
        ]
    except Exception:
        return []


def _collect_volumes(conn: openstack.connection.Connection, server_id: str) -> list[dict]:
    """인스턴스에 연결된 볼륨 상태를 수집한다. 실패 시 빈 목록."""
    try:
        attachments = nova.list_volume_attachments(conn, server_id)
    except Exception as exc:
        logger.warning("볼륨 attachment 목록 수집 실패: %s", exc)
        return []

    result = []
    for att in attachments:
        vol_id = att.get("volume_id")
        if not vol_id:
            continue
        try:
            vol = cinder.get_volume(conn, vol_id)
            result.append(
                {
                    "volume_id": vol_id,
                    "device": att.get("device"),
                    "status": (vol.status or "").lower(),
                    "bootable": getattr(vol, "is_bootable", False) or (vol.bootable == "true"),
                    "attachments": vol.attachments or [],
                    "delete_on_termination": att.get("delete_on_termination", False),
                }
            )
        except Exception as exc:
            logger.warning("볼륨 %s 상태 수집 실패: %s", vol_id, exc)
            result.append(
                {
                    "volume_id": vol_id,
                    "device": att.get("device"),
                    "status": "unknown",
                    "bootable": False,
                    "attachments": [],
                    "delete_on_termination": att.get("delete_on_termination", False),
                }
            )
    return result


def _collect_ports(conn: openstack.connection.Connection, server_id: str) -> list[dict]:
    """인스턴스 포트를 수집한다 (vif_type 포함). admin conn 필요. 실패 시 빈 목록."""
    try:
        ports = list(conn.network.ports(device_id=server_id))
        return [
            {
                "id": p.id,
                "status": (getattr(p, "status", "") or "").upper(),
                "binding_vif_type": getattr(p, "binding_vif_type", None),
            }
            for p in ports
        ]
    except Exception as exc:
        logger.warning("포트 수집 실패: %s", exc)
        return []


# ---------------------------------------------------------------------------
# 안전 검사
# ---------------------------------------------------------------------------


def _check_is_error_state(srv: dict | None) -> dict:
    if srv is None:
        return {
            "key": "is_error_state",
            "label": "인스턴스 ERROR 상태",
            "passed": False,
            "detail": "서버 정보를 가져올 수 없습니다",
        }
    passed = srv["status"] == "ERROR"
    return {
        "key": "is_error_state",
        "label": "인스턴스 ERROR 상태",
        "passed": passed,
        "detail": f"현재 상태: {srv['status']}" if not passed else "ERROR 상태 확인됨",
    }


def _check_volume_backed(srv: dict | None, volumes: list[dict]) -> dict:
    """볼륨 부팅 여부 확인 — flavor disk=0이면 데이터가 Ceph RBD에 보존됨."""
    if srv is None:
        return {
            "key": "volume_backed",
            "label": "볼륨 부팅 (데이터 보존)",
            "passed": False,
            "detail": "서버 정보를 가져올 수 없습니다",
        }

    flavor_disk = srv.get("flavor_disk", -1)
    has_boot_volume = any(v.get("bootable") for v in volumes)
    # flavor disk=0이거나, image 없고 부팅 볼륨이 있으면 볼륨 부팅
    is_volume_backed = (flavor_disk == 0) or (not srv.get("image_id") and has_boot_volume)

    return {
        "key": "volume_backed",
        "label": "볼륨 부팅 (데이터 보존)",
        "passed": is_volume_backed,
        "detail": "볼륨 부팅 확인 — 데이터는 Ceph RBD에 보존됨"
        if is_volume_backed
        else f"로컬 디스크 사용 가능성 있음 (flavor disk={flavor_disk}GB). 수동 확인 권장",
    }


def _check_ports_healthy(ports: list[dict]) -> dict:
    """모든 포트 ACTIVE이고 binding_failed/unbound 없어야 함."""
    bad_vif = {"binding_failed", "unbound"}
    failed_ports = [
        p
        for p in ports
        if (p.get("status") or "").upper() != "ACTIVE" or (p.get("binding_vif_type") or "").lower() in bad_vif
    ]
    if not ports:
        return {
            "key": "ports_healthy",
            "label": "포트 바인딩 정상",
            "passed": True,
            "detail": "포트 없음 또는 조회 불가 — 통과 처리",
        }
    passed = len(failed_ports) == 0
    return {
        "key": "ports_healthy",
        "label": "포트 바인딩 정상",
        "passed": passed,
        "detail": "모든 포트 ACTIVE + 바인딩 정상"
        if passed
        else f"비정상 포트 {len(failed_ports)}개: "
        + ", ".join(
            f"{p['id'][:8]} (vif={p.get('binding_vif_type')}, status={p.get('status')})" for p in failed_ports[:3]
        ),
    }


def _check_no_live_migration_risk(migrations: list[dict]) -> dict:
    """최근 error 마이그레이션이 live-migration이 아니면 통과 (이중 기동 위험 없음)."""
    error_migs = [m for m in migrations if m["status"] == "error"]
    if not error_migs:
        return {
            "key": "no_live_migration_risk",
            "label": "이중 기동 위험 없음 (cold/resize 실패)",
            "passed": True,
            "detail": "실패한 마이그레이션 없음",
        }
    latest = error_migs[0]
    is_risky = (latest.get("migration_type") or "").lower() in _RISKY_MIGRATION_TYPES
    return {
        "key": "no_live_migration_risk",
        "label": "이중 기동 위험 없음 (cold/resize 실패)",
        "passed": not is_risky,
        "detail": f"최근 실패 타입: {latest.get('migration_type')} — "
        + (
            "라이브 마이그레이션 실패 시 소스 도메인 잔존 가능. 수동 확인 필요"
            if is_risky
            else "cold/resize 실패 — 소스에 실행 도메인 없음"
        ),
    }


def _check_no_task_in_progress(srv: dict | None, active_migs: list[dict]) -> dict:
    """task_state=None이고 진행 중 마이그레이션 없어야 함."""
    if srv is None:
        return {
            "key": "no_task_in_progress",
            "label": "진행 중 작업 없음",
            "passed": False,
            "detail": "서버 정보를 가져올 수 없습니다",
        }

    task_state = srv.get("task_state")
    has_active = len(active_migs) > 0
    passed = task_state is None and not has_active
    detail_parts = []
    if task_state:
        detail_parts.append(f"task_state={task_state}")
    if has_active:
        detail_parts.append(f"진행 중 마이그레이션 {len(active_migs)}개")
    return {
        "key": "no_task_in_progress",
        "label": "진행 중 작업 없음",
        "passed": passed,
        "detail": "진행 중 작업 없음" if passed else "진행 중 작업 있음: " + ", ".join(detail_parts),
    }


# ---------------------------------------------------------------------------
# 시나리오 판정
# ---------------------------------------------------------------------------


def _determine_scenario(
    srv: dict | None,
    volumes: list[dict],
    migrations: list[dict],
) -> tuple[str, str, list[dict]]:
    """복구 시나리오와 단계 목록을 반환한다.

    Returns:
        (scenario_key, scenario_description, steps)
    """
    if srv is None or srv["status"] != "ERROR":
        return (
            "manual_review",
            "ERROR 상태가 아니거나 서버 정보를 가져올 수 없어 자동 복구를 수행할 수 없습니다.",
            [{"action": "manual", "params": {}, "description": "Nova, Cinder, Neutron 로그를 직접 확인하세요."}],
        )

    error_migs = [m for m in migrations if m["status"] == "error"]
    stuck_vols = [v for v in volumes if v["status"] in _STUCK_VOLUME_STATUSES]
    normal_vols = [v for v in volumes if v["status"] not in _STUCK_VOLUME_STATUSES and v["status"] != "unknown"]

    if error_migs and stuck_vols:
        latest_mig = error_migs[0]
        steps = []
        for v in stuck_vols:
            steps.append(
                {
                    "action": "reset_volume_state",
                    "params": {"volume_id": v["volume_id"], "status": "in-use", "attach_status": "attached"},
                    "description": f"볼륨 {v['volume_id'][:8]} 상태를 in-use/attached로 강제 복구",
                }
            )
        steps.append(
            {
                "action": "reset_server_state",
                "params": {"state": "active"},
                "description": "인스턴스 상태를 active로 강제 복구",
            }
        )
        steps.append(
            {
                "action": "hard_reboot",
                "params": {},
                "description": "하드 리부트 — nova-compute가 RBD connection info로 도메인 재생성",
            }
        )
        return (
            "migration_failed_volume_stuck",
            f"마이그레이션 실패({latest_mig.get('migration_type')}, "
            f"{latest_mig.get('source_compute')} → {latest_mig.get('dest_compute')}) 후 "
            f"볼륨 {len(stuck_vols)}개가 {stuck_vols[0]['status']} 상태로 고착됨. "
            "볼륨 상태 복구 → 서버 상태 복구 → 하드 리부트 순으로 진행합니다.",
            steps,
        )

    if stuck_vols:
        steps = []
        for v in stuck_vols:
            steps.append(
                {
                    "action": "reset_volume_state",
                    "params": {"volume_id": v["volume_id"], "status": "in-use", "attach_status": "attached"},
                    "description": f"볼륨 {v['volume_id'][:8]} 상태를 in-use/attached로 강제 복구",
                }
            )
        steps.append(
            {
                "action": "reset_server_state",
                "params": {"state": "active"},
                "description": "인스턴스 상태를 active로 강제 복구",
            }
        )
        steps.append(
            {
                "action": "hard_reboot",
                "params": {},
                "description": "하드 리부트 — nova-compute가 도메인을 재생성합니다",
            }
        )
        return (
            "volume_stuck",
            f"볼륨 {len(stuck_vols)}개가 {stuck_vols[0]['status']} 상태로 고착된 채 ERROR 상태입니다. "
            "볼륨 상태 복구 → 서버 상태 복구 → 하드 리부트 순으로 진행합니다.",
            steps,
        )

    if not stuck_vols and len(normal_vols) == len(volumes):
        steps = [
            {
                "action": "reset_server_state",
                "params": {"state": "active"},
                "description": "인스턴스 상태를 active로 강제 복구",
            },
            {
                "action": "hard_reboot",
                "params": {},
                "description": "하드 리부트 — nova-compute가 도메인 상태를 동기화합니다",
            },
        ]
        return (
            "generic_error",
            "볼륨과 포트는 정상이나 인스턴스가 ERROR 상태입니다. 서버 상태 복구 → 하드 리부트로 복구를 시도합니다.",
            steps,
        )

    return (
        "manual_review",
        "자동 복구 조건에 해당하지 않습니다. Nova fault 메시지와 Cinder/Neutron 로그를 확인하세요.",
        [{"action": "manual", "params": {}, "description": "수동 점검이 필요합니다."}],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_error_instance(
    conn: openstack.connection.Connection,
    server_id: str,
) -> dict:
    """ERROR 인스턴스를 진단하고 복구 계획을 반환한다.

    모든 수집은 fail-soft — 개별 조회 실패 시 해당 check를 fail 처리하고 계속한다.
    ERROR가 아닌 인스턴스도 200으로 응답하고 is_error_state fail을 통해 표현한다.
    """
    srv = _collect_server(conn, server_id)
    migrations = _collect_migrations(conn, server_id)
    active_migs = _collect_active_migrations(conn, server_id)
    volumes = _collect_volumes(conn, server_id)
    ports = _collect_ports(conn, server_id)

    checks = [
        _check_is_error_state(srv),
        _check_volume_backed(srv, volumes),
        _check_ports_healthy(ports),
        _check_no_live_migration_risk(migrations),
        _check_no_task_in_progress(srv, active_migs),
    ]

    scenario, scenario_description, steps = _determine_scenario(srv, volumes, migrations)
    auto_executable = scenario != "manual_review" and all(c["passed"] for c in checks)

    error_migs = [m for m in migrations if m["status"] == "error"]
    last_error_migration = error_migs[0] if error_migs else None
    placement_note: str | None = None
    if last_error_migration and last_error_migration.get("source_compute"):
        src = last_error_migration["source_compute"]
        placement_note = (
            f"소스 호스트 '{src}'에 잔여 placement 할당이 남았을 수 있습니다. "
            f"`openstack resource provider allocation show {server_id}` 로 확인 후 "
            "중복 항목이 있으면 수동 정리를 권장합니다."
        )

    return {
        "server": {
            "id": srv["id"] if srv else server_id,
            "name": srv["name"] if srv else "",
            "status": srv["status"] if srv else "UNKNOWN",
            "compute_host": srv["compute_host"] if srv else None,
            "fault": srv["fault"] if srv else None,
        }
        if srv
        else {"id": server_id, "name": "", "status": "UNKNOWN", "compute_host": None, "fault": None},
        "last_error_migration": last_error_migration,
        "volumes": volumes,
        "ports": ports,
        "checks": checks,
        "scenario": scenario,
        "scenario_description": scenario_description,
        "steps": steps,
        "auto_executable": auto_executable,
        "placement_note": placement_note,
    }


def execute_recovery(
    conn: openstack.connection.Connection,
    server_id: str,
) -> dict:
    """복구를 실행한다.

    실행 직전 분석을 재수행해 auto_executable을 재검증한다(fail-closed).
    클라이언트가 보낸 step 목록을 신뢰하지 않는다.

    Raises:
        ValueError: auto_executable=False인 경우 — 라우터에서 409로 변환.
    """
    analysis = analyze_error_instance(conn, server_id)
    if not analysis["auto_executable"]:
        failed = [c for c in analysis["checks"] if not c["passed"]]
        reasons = "; ".join(c["label"] for c in failed)
        raise ValueError(f"자동 복구 조건 미충족 — {reasons}")

    steps = analysis["steps"]
    executed_steps: list[dict] = []

    for step in steps:
        action = step["action"]
        params = step.get("params", {})
        description = step.get("description", action)

        if action == "manual":
            executed_steps.append(
                {"action": action, "description": description, "status": "skipped", "detail": "수동 단계"}
            )
            continue

        # 화이트리스트 검사 (방어적 코딩)
        if action not in {"reset_volume_state", "reset_server_state", "hard_reboot"}:
            executed_steps.append(
                {"action": action, "description": description, "status": "skipped", "detail": "알 수 없는 액션"}
            )
            continue

        try:
            if action == "reset_volume_state":
                volume_id = params["volume_id"]
                status = params.get("status", "in-use")
                attach_status = params.get("attach_status")
                cinder.reset_volume_status(conn, volume_id, status, attach_status)
                executed_steps.append(
                    {
                        "action": action,
                        "description": description,
                        "status": "success",
                        "detail": f"볼륨 {volume_id[:8]} → {status}",
                    }
                )

            elif action == "reset_server_state":
                state = params.get("state", "active")
                nova.reset_server_state(conn, server_id, state)
                # ERROR 상태에서 reboot은 실패하므로 상태 전환 확인
                try:
                    refreshed = conn.compute.get_server(server_id)
                    new_status = (getattr(refreshed, "status", "") or "").upper()
                except Exception:
                    new_status = "UNKNOWN"
                executed_steps.append(
                    {
                        "action": action,
                        "description": description,
                        "status": "success",
                        "detail": f"서버 상태 → {new_status}",
                    }
                )

            elif action == "hard_reboot":
                nova.reboot_server(conn, server_id, "HARD")
                executed_steps.append(
                    {
                        "action": action,
                        "description": description,
                        "status": "success",
                        "detail": "하드 리부트 요청 완료",
                    }
                )

        except Exception as exc:
            logger.warning("복구 단계 '%s' 실패: %s", action, exc)
            executed_steps.append(
                {"action": action, "description": description, "status": "failed", "detail": str(exc)[:200]}
            )
            # 실패 시 즉시 중단, 나머지는 skipped
            remaining = steps[len(executed_steps) :]
            for rem in remaining:
                executed_steps.append(
                    {
                        "action": rem["action"],
                        "description": rem.get("description", rem["action"]),
                        "status": "skipped",
                        "detail": "이전 단계 실패로 건너뜀",
                    }
                )
            return {
                "executed": False,
                "scenario": analysis["scenario"],
                "steps": executed_steps,
            }

    return {
        "executed": True,
        "scenario": analysis["scenario"],
        "steps": executed_steps,
    }
