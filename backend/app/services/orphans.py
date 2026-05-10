"""Admin orphan resource detection — 분리된 FIP / 장기 미사용 volume 검색 및 정리.

Race-safe cleanup: volume 삭제 직전 재조회로 attachments/status 검증.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.models.orphans import OrphanFipInfo, OrphanVolumeInfo
from app.services import cinder, neutron

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
