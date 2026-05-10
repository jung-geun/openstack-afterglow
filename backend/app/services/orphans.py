"""Admin orphan resource detection — FIP / volume / Manila share / Security group 검색 및 정리.

Race-safe cleanup: 삭제 직전 재조회로 일관성 검증 (attachments / project / snapshot / attach).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.models.orphans import (
    OrphanFipInfo,
    OrphanSecurityGroupInfo,
    OrphanShareInfo,
    OrphanVolumeInfo,
)
from app.services import cinder, keystone, manila, neutron
from app.services.neutron import AFTERGLOW_MANAGED_TAG

if TYPE_CHECKING:
    import openstack


def _parse_created_at(value: str | None) -> datetime | None:
    """OpenStack created_at 문자열을 UTC aware datetime으로 변환. 실패 시 None."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Cinder/Neutron created_at은 보통 "2026-04-01T12:34:56" 또는 "...Z" 형식.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _age_days(created_at: str | None, *, now: datetime | None = None) -> int:
    """created_at 부터 경과 일수. 파싱 실패 시 0 반환."""
    dt = _parse_created_at(created_at)
    if dt is None:
        return 0
    ref = now or datetime.now(UTC)
    delta = ref - dt
    return max(0, delta.days)


# ---------------------------------------------------------------------------
# Floating IPs — port_id NULL 즉시 orphan
# ---------------------------------------------------------------------------


def find_orphan_floating_ips(conn: openstack.connection.Connection) -> list[OrphanFipInfo]:
    """`port_id IS NULL` 인 모든 FIP를 admin 가시성으로 수집."""
    out: list[OrphanFipInfo] = []
    now = datetime.now(UTC)
    for f in conn.network.ips():
        if getattr(f, "port_id", None):
            continue
        created_at = getattr(f, "created_at", None)
        out.append(
            OrphanFipInfo(
                id=f.id,
                address=getattr(f, "floating_ip_address", "") or "",
                project_id=getattr(f, "project_id", None),
                created_at=str(created_at) if created_at else None,
                age_days=_age_days(created_at, now=now),
            )
        )
    return out


def cleanup_floating_ips(conn: openstack.connection.Connection, ids: list[str]) -> tuple[list[str], list[dict]]:
    """주어진 FIP들을 일괄 삭제. 부분 실패 시 failed[]에 분리."""
    deleted: list[str] = []
    failed: list[dict] = []
    for fip_id in ids:
        try:
            neutron.delete_floating_ip(conn, fip_id)
            deleted.append(fip_id)
        except Exception as e:
            failed.append({"id": fip_id, "error": str(e)})
    return deleted, failed


# ---------------------------------------------------------------------------
# Cinder volumes — status=available + attachments=[] + age >= min_age_days
# ---------------------------------------------------------------------------


def find_orphan_volumes(
    conn: openstack.connection.Connection,
    min_age_days: int = 14,
) -> list[OrphanVolumeInfo]:
    """장기 미사용 volume을 admin 전(全) 프로젝트 범위에서 수집."""
    out: list[OrphanVolumeInfo] = []
    now = datetime.now(UTC)
    for v in conn.block_storage.volumes(details=True, all_projects=True, status="available"):
        attachments = list(getattr(v, "attachments", None) or [])
        if attachments:
            continue
        created_at = getattr(v, "created_at", None)
        age = _age_days(created_at, now=now)
        if age < min_age_days:
            continue
        out.append(
            OrphanVolumeInfo(
                id=v.id,
                name=getattr(v, "name", None) or None,
                size_gb=int(getattr(v, "size", 0) or 0),
                project_id=getattr(v, "project_id", None),
                status=getattr(v, "status", "") or "",
                created_at=str(created_at) if created_at else None,
                age_days=age,
            )
        )
    return out


def cleanup_volumes(conn: openstack.connection.Connection, ids: list[str]) -> tuple[list[str], list[dict]]:
    """주어진 volume들을 race-safe로 삭제.

    각 volume별로:
      1) cinder.get_volume 재조회
      2) attachments != [] or status != "available" → failed (delete 호출 안 함)
      3) cinder.delete_volume 호출. 예외는 failed 로 회수.
    """
    deleted: list[str] = []
    failed: list[dict] = []
    for vid in ids:
        try:
            current = cinder.get_volume(conn, vid)
        except Exception as e:
            failed.append({"id": vid, "error": f"재조회 실패: {e}"})
            continue

        if list(current.attachments or []):
            failed.append({"id": vid, "error": "정리 보류: attachments 존재 (race)"})
            continue
        if current.status != "available":
            failed.append({"id": vid, "error": f"정리 보류: status={current.status}"})
            continue

        try:
            cinder.delete_volume(conn, vid)
            deleted.append(vid)
        except Exception as e:
            failed.append({"id": vid, "error": str(e)})
    return deleted, failed


# ---------------------------------------------------------------------------
# Manila shares — Keystone 프로젝트 부재 시 orphan
# ---------------------------------------------------------------------------


def find_orphan_manila_shares(conn: openstack.connection.Connection) -> list[OrphanShareInfo]:
    """admin scope 전(全) project Manila share 중 project 삭제로 잔존한 것을 수집.

    `is_public=True` share는 운영자/타 프로젝트가 의도적으로 공유한 자원이므로 제외.
    """
    valid_projects = keystone.list_all_project_ids()
    shares = manila.list_file_storages(conn, all_tenants=True)
    out: list[OrphanShareInfo] = []
    now = datetime.now(UTC)
    for s in shares:
        if s.is_public:
            continue
        if not s.project_id or s.project_id in valid_projects:
            continue
        out.append(
            OrphanShareInfo(
                id=s.id,
                name=s.name or None,
                size_gb=int(s.size or 0),
                project_id=s.project_id,
                status=s.status or "",
                created_at=s.created_at,
                age_days=_age_days(s.created_at, now=now),
            )
        )
    return out


def cleanup_manila_shares(conn: openstack.connection.Connection, ids: list[str]) -> tuple[list[str], list[dict]]:
    """Manila share를 race-safe로 삭제.

    각 share별로:
      1) get_file_storage 재조회 (없으면 이미 삭제됨)
      2) project_id가 여전히 Keystone 프로젝트 셋에 없는지 (있으면 project 복구된 것)
      3) snapshot 0건 확인 (snapshot 보존 우선)
      4) status in {available, error}
      5) 통과 시 delete_file_storage
    """
    deleted: list[str] = []
    failed: list[dict] = []
    try:
        valid_projects = keystone.list_all_project_ids()
    except Exception as e:
        # Keystone 자체 호출 실패 — 전 항목 fail (race 위험 회피)
        return deleted, [{"id": sid, "error": f"Keystone 조회 실패: {e}"} for sid in ids]

    for sid in ids:
        try:
            current = manila.get_file_storage(conn, sid)
        except Exception as e:
            # 재조회 실패: 이미 삭제됐거나 권한 문제 — 보수적으로 fail.
            failed.append({"id": sid, "error": f"재조회 실패: {e}"})
            continue

        if current.project_id and current.project_id in valid_projects:
            failed.append({"id": sid, "error": "정리 보류: project가 복구됨"})
            continue

        try:
            snapshots = manila.list_share_snapshots(conn, file_storage_id=sid)
        except Exception as e:
            failed.append({"id": sid, "error": f"snapshot 조회 실패: {e}"})
            continue
        if snapshots:
            failed.append({"id": sid, "error": f"정리 보류: snapshot {len(snapshots)}건 존재"})
            continue

        if current.status not in {"available", "error"}:
            failed.append({"id": sid, "error": f"정리 보류: status={current.status}"})
            continue

        try:
            manila.delete_file_storage(conn, sid)
            deleted.append(sid)
        except Exception as e:
            failed.append({"id": sid, "error": str(e)})
    return deleted, failed


# ---------------------------------------------------------------------------
# Security Groups — afterglow description marker + attach 0건
# ---------------------------------------------------------------------------


def _build_attached_sg_set(conn: openstack.connection.Connection) -> set[str]:
    """모든 port를 한 번 fetch하여 attach된 SG ID 셋 반환 (admin scope cross-project)."""
    attached: set[str] = set()
    for p in conn.network.ports():
        for sg_id in p.security_group_ids or []:
            attached.add(sg_id)
    return attached


def _has_marker(description: str | None) -> bool:
    return (description or "").endswith(AFTERGLOW_MANAGED_TAG)


def find_orphan_security_groups(
    conn: openstack.connection.Connection,
) -> list[OrphanSecurityGroupInfo]:
    """afterglow가 자동 생성한 SG 중 어떤 port에도 attach 안 된 것을 수집.

    description marker(`[afterglow-managed]`)가 끝에 붙은 SG만 후보로 간주.
    사용자가 만든 SG는 marker 부재로 자동 제외.
    """
    attached = _build_attached_sg_set(conn)
    out: list[OrphanSecurityGroupInfo] = []
    now = datetime.now(UTC)
    for sg in conn.network.security_groups():
        if not _has_marker(getattr(sg, "description", None)):
            continue
        if sg.id in attached:
            continue
        created_at = getattr(sg, "created_at", None)
        out.append(
            OrphanSecurityGroupInfo(
                id=sg.id,
                name=getattr(sg, "name", "") or "",
                description=getattr(sg, "description", None),
                project_id=getattr(sg, "project_id", None),
                created_at=str(created_at) if created_at else None,
                age_days=_age_days(created_at, now=now),
            )
        )
    return out


def cleanup_security_groups(conn: openstack.connection.Connection, ids: list[str]) -> tuple[list[str], list[dict]]:
    """Security Group을 race-safe로 삭제.

    1) 모든 port 한 번 fetch → attached SG id 셋 (SDK list-query 가정 회피)
    2) 각 SG 재조회 후 marker 재확인
    3) attached 셋에 포함되면 fail
    4) 통과 시 delete_security_group
    """
    deleted: list[str] = []
    failed: list[dict] = []
    try:
        attached = _build_attached_sg_set(conn)
    except Exception as e:
        return deleted, [{"id": sid, "error": f"port 조회 실패: {e}"} for sid in ids]

    for sg_id in ids:
        try:
            current = conn.network.get_security_group(sg_id)
        except Exception as e:
            failed.append({"id": sg_id, "error": f"재조회 실패: {e}"})
            continue

        if not _has_marker(getattr(current, "description", None)):
            failed.append({"id": sg_id, "error": "정리 보류: marker 없음 — 사용자 SG 가능성"})
            continue

        if sg_id in attached:
            failed.append({"id": sg_id, "error": "정리 보류: attach 발생 (race)"})
            continue

        try:
            neutron.delete_security_group(conn, sg_id)
            deleted.append(sg_id)
        except Exception as e:
            failed.append({"id": sg_id, "error": str(e)})
    return deleted, failed
