"""볼륨 자동 백업 서비스.

Redis에 볼륨별 자동 백업 설정을 저장하고, 백그라운드 워커에서 주기적으로 백업을 실행한다.

보존 정책 (볼륨당 최대 5개):
  - daily  : 최근 일 단위 백업 최대 2개 유지
  - weekly : 최근 주 단위 백업 최대 2개 유지
  - monthly: 최근 월 단위 백업 최대 1개 유지

Redis 키:
  afterglow:auto_backup:config:{project_id}:{volume_id}  → JSON 설정
  afterglow:auto_backup:all_configs                      → set of "project_id:volume_id"
"""

import json
import logging
from datetime import UTC, datetime

import openstack

from app.services import cinder
from app.services.cache import _get_redis

_logger = logging.getLogger(__name__)

_PREFIX = "afterglow:auto_backup"
_ALL_KEY = f"{_PREFIX}:all_configs"


# ────────────────────────────────────────────
# Config CRUD
# ────────────────────────────────────────────


async def enable_auto_backup(
    project_id: str, volume_id: str, max_daily: int = 2, max_weekly: int = 2, max_monthly: int = 1
) -> dict:
    """볼륨 자동 백업 활성화. 설정을 Redis에 저장."""
    config = {
        "volume_id": volume_id,
        "project_id": project_id,
        "enabled": True,
        "max_daily": max_daily,
        "max_weekly": max_weekly,
        "max_monthly": max_monthly,
        "created_at": datetime.now(UTC).isoformat(),
    }
    r = await _get_redis()
    key = f"{_PREFIX}:config:{project_id}:{volume_id}"
    await r.set(key, json.dumps(config))
    await r.sadd(_ALL_KEY, f"{project_id}:{volume_id}")
    return config


async def disable_auto_backup(project_id: str, volume_id: str) -> None:
    """볼륨 자동 백업 비활성화. Redis에서 설정 삭제."""
    r = await _get_redis()
    key = f"{_PREFIX}:config:{project_id}:{volume_id}"
    await r.delete(key)
    await r.srem(_ALL_KEY, f"{project_id}:{volume_id}")


async def get_auto_backup_config(project_id: str, volume_id: str) -> dict | None:
    """볼륨의 자동 백업 설정 조회."""
    r = await _get_redis()
    key = f"{_PREFIX}:config:{project_id}:{volume_id}"
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def list_auto_backup_configs(project_id: str) -> list[dict]:
    """프로젝트의 모든 자동 백업 설정 조회."""
    r = await _get_redis()
    members = await r.smembers(_ALL_KEY)
    configs = []
    for member in members:
        pid, vid = member.split(":", 1)
        if pid != project_id:
            continue
        cfg = await get_auto_backup_config(pid, vid)
        if cfg:
            configs.append(cfg)
    return configs


async def list_all_auto_backup_configs() -> list[dict]:
    """전체 프로젝트의 모든 자동 백업 설정 조회 (백그라운드 워커용)."""
    r = await _get_redis()
    members = await r.smembers(_ALL_KEY)
    configs = []
    for member in members:
        pid, vid = member.split(":", 1)
        cfg = await get_auto_backup_config(pid, vid)
        if cfg:
            configs.append(cfg)
    return configs


# ────────────────────────────────────────────
# Backup 이름 파싱 / 분류
# ────────────────────────────────────────────


def _make_backup_name(volume_id: str, tier: str) -> str:
    """tier: daily | weekly | monthly"""
    date = datetime.now(UTC).strftime("%Y%m%d")
    return f"auto_{volume_id[:8]}_{tier}_{date}"


def _is_auto_backup(backup: dict, volume_id: str, tier: str) -> bool:
    name = backup.get("name", "")
    prefix = f"auto_{volume_id[:8]}_{tier}_"
    return name.startswith(prefix)


def _backup_date(backup: dict) -> datetime | None:
    """백업의 created_at을 datetime으로 반환."""
    ts = backup.get("created_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


# ────────────────────────────────────────────
# Backup Cycle
# ────────────────────────────────────────────


async def run_backup_cycle(
    conn: openstack.connection.Connection, project_id: str, volume_id: str, config: dict
) -> None:
    """한 볼륨에 대한 자동 백업 사이클 실행.

    1. 기존 자동 백업 목록 조회
    2. 각 tier(daily/weekly/monthly)에 대해:
       a. 마지막 백업 시각 확인 → 간격 초과 시 신규 백업 생성
       b. 보존 개수 초과 시 오래된 것부터 삭제
    """
    import asyncio

    now = datetime.now(UTC)

    try:
        all_backups = await asyncio.to_thread(cinder.list_backups, conn)
    except Exception as e:
        _logger.warning("auto_backup: 백업 목록 조회 실패 (volume=%s): %s", volume_id, e)
        return

    # 이 볼륨의 자동 백업만 필터
    vol_backups = [b for b in all_backups if b.get("volume_id") == volume_id]

    tiers = [
        ("daily", config.get("max_daily", 2), 24 * 3600),
        ("weekly", config.get("max_weekly", 2), 7 * 24 * 3600),
        ("monthly", config.get("max_monthly", 1), 30 * 24 * 3600),
    ]

    for tier, max_count, min_interval in tiers:
        tier_backups = [b for b in vol_backups if _is_auto_backup(b, volume_id, tier)]
        # created_at 기준 최신 순 정렬
        tier_backups.sort(key=lambda b: b.get("created_at", ""), reverse=True)

        # 신규 백업 필요 여부 판단
        should_create = True
        if tier_backups:
            last_date = _backup_date(tier_backups[0])
            if last_date and (now - last_date).total_seconds() < min_interval:
                should_create = False

        if should_create:
            name = _make_backup_name(volume_id, tier)
            try:
                # daily는 incremental, weekly/monthly는 full
                incremental = tier == "daily" and bool(tier_backups)
                await asyncio.to_thread(cinder.create_backup, conn, volume_id, name, f"자동 백업 ({tier})", incremental)
                _logger.info("auto_backup: %s 백업 생성 완료 (volume=%s, name=%s)", tier, volume_id, name)
                # 방금 생성한 것 포함 재조회 필요 — 목록에 추가 처리
                tier_backups = [{"name": name, "created_at": now.isoformat(), "volume_id": volume_id}] + tier_backups
            except Exception as e:
                _logger.warning("auto_backup: %s 백업 생성 실패 (volume=%s): %s", tier, volume_id, e)

        # 보존 개수 초과분 삭제 (오래된 것부터)
        to_delete = tier_backups[max_count:]
        for old_backup in to_delete:
            bid = old_backup.get("id")
            if not bid:
                continue
            # 아직 available 상태가 아닌 백업은 삭제 건너뜀
            if old_backup.get("status") not in ("available", None):
                continue
            try:
                await asyncio.to_thread(cinder.delete_backup, conn, bid)
                _logger.info("auto_backup: 오래된 %s 백업 삭제 (volume=%s, id=%s)", tier, volume_id, bid)
            except Exception as e:
                _logger.warning("auto_backup: %s 백업 삭제 실패 (volume=%s, id=%s): %s", tier, volume_id, bid, e)
