"""인스턴스 헬스 토큰 발급/검증/폐기 + Redis 캐시."""

import json
import logging
import secrets
from datetime import UTC, datetime

from app.models.instance_health import InstanceHealth, InstanceHealthReport

_logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "afterglow:health:token:"
_INSTANCE_PREFIX = "afterglow:health:instance:"
_RESULT_PREFIX = "afterglow:health:result:"
# 절대 만료 7일 — sliding window 제거 (이전: 30일 sliding 으로 사실상 영구 토큰).
# VM userdata 가 노출돼도 7일 후 토큰이 만료되어 cephx rotate 권한 무효화.
# 인스턴스가 7일 이상 살아있으면 health_check.sh 의 재발급 흐름이 새 토큰을 받음.
_TOKEN_TTL = 86400 * 7
_RESULT_TTL = 1800  # 30분


async def _redis():
    from app.services.cache import _get_client

    return _get_client()


# ---------------------------------------------------------------------------
# 토큰 lifecycle
# ---------------------------------------------------------------------------


async def issue_report_token(instance_id: str, project_id: str) -> str:
    """헬스 리포트 토큰 발급. 이미 존재하면 기존 토큰을 폐기 후 재발급."""
    await revoke_report_token_by_instance(instance_id)

    token = secrets.token_urlsafe(32)
    r = await _redis()
    payload = json.dumps({"instance_id": instance_id, "project_id": project_id})
    await r.setex(f"{_TOKEN_PREFIX}{token}", _TOKEN_TTL, payload)
    await r.setex(f"{_INSTANCE_PREFIX}{instance_id}", _TOKEN_TTL, token)
    return token


async def verify_report_token(token: str) -> dict | None:
    """토큰 검증. 성공 시 {instance_id, project_id} 반환.

    sliding TTL 갱신은 제거 (이전: 매 호출마다 r.expire(7d) 로 사실상 영구 토큰).
    토큰은 발급 후 절대 만료 7일 — 만료 전 인스턴스 부팅 시 재발급되도록 cloud-init
    측에서 처리.
    """
    try:
        r = await _redis()
        raw = await r.get(f"{_TOKEN_PREFIX}{token}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        _logger.warning("instance_health: 토큰 검증 실패", exc_info=True)
        return None


async def revoke_report_token_by_instance(instance_id: str) -> None:
    """인스턴스 삭제 시 역인덱스로 토큰 lookup 후 두 키 모두 삭제."""
    try:
        r = await _redis()
        token = await r.get(f"{_INSTANCE_PREFIX}{instance_id}")
        if token:
            if isinstance(token, bytes):
                token = token.decode()
            await r.delete(f"{_TOKEN_PREFIX}{token}")
        await r.delete(f"{_INSTANCE_PREFIX}{instance_id}")
    except Exception:
        _logger.warning("instance_health: 토큰 폐기 실패 (instance=%s)", instance_id, exc_info=True)


# ---------------------------------------------------------------------------
# 헬스 결과 캐시
# ---------------------------------------------------------------------------


async def store_health_result(instance_id: str, report: InstanceHealthReport) -> None:
    """헬스 리포트를 Redis에 저장 (TTL 30분)."""
    try:
        r = await _redis()
        await r.setex(f"{_RESULT_PREFIX}{instance_id}", _RESULT_TTL, report.model_dump_json())
    except Exception:
        _logger.warning("instance_health: Redis 저장 실패 (instance=%s)", instance_id, exc_info=True)


async def get_health_result(instance_id: str) -> InstanceHealth | None:
    """Redis에서 헬스 결과 조회 + status 판정."""
    try:
        r = await _redis()
        raw = await r.get(f"{_RESULT_PREFIX}{instance_id}")
        if not raw:
            return None
        report = InstanceHealthReport.model_validate_json(raw)
        return _evaluate(instance_id, report)
    except Exception:
        _logger.warning("instance_health: Redis 조회 실패 (instance=%s)", instance_id, exc_info=True)
        return None


async def list_health_results(instance_ids: list[str]) -> list[InstanceHealth]:
    """여러 인스턴스 헬스 결과 일괄 조회."""
    results = []
    for iid in instance_ids:
        h = await get_health_result(iid)
        if h is not None:
            results.append(h)
    return results


# ---------------------------------------------------------------------------
# 내부: status 판정 로직
# ---------------------------------------------------------------------------

_STALE_MINUTES = 15


def _evaluate(instance_id: str, report: InstanceHealthReport) -> InstanceHealth:
    """InstanceHealthReport → InstanceHealth (status + warnings 판정)."""
    warnings: list[str] = []
    status = "healthy"
    checked_at = datetime.now(UTC).isoformat()

    # stale 판정
    try:
        reported_dt = datetime.fromisoformat(report.reported_at.replace("Z", "+00:00"))
        age_min = (datetime.now(UTC) - reported_dt).total_seconds() / 60
        if age_min > _STALE_MINUTES:
            return InstanceHealth(
                instance_id=instance_id,
                status="stale",
                warnings=[f"마지막 보고 후 {age_min:.0f}분 경과"],
                overlay_mounted=report.overlay_mounted,
                upper_used_bytes=report.upper_used_bytes,
                upper_total_bytes=report.upper_total_bytes,
                upper_usage_pct=report.upper_usage_pct,
                shares=report.shares,
                kernel=report.kernel,
                uptime_seconds=report.uptime_seconds,
                reported_at=report.reported_at,
                checked_at=checked_at,
            )
    except Exception:
        pass

    if not report.overlay_mounted:
        status = "error"
        warnings.append("OverlayFS가 마운트되지 않았습니다")

    for share in report.shares:
        if share.status == "unreachable":
            status = "error"
            warnings.append(f"공유({share.name}) 접근 불가")
        elif share.status == "timeout":
            status = "error"
            warnings.append(f"공유({share.name}) 타임아웃")

    if report.upper_usage_pct >= 95:
        status = "error"
        warnings.append(f"Upper 볼륨 사용률 {report.upper_usage_pct:.0f}% (임계값 95%)")
    elif report.upper_usage_pct >= 90:
        if status == "healthy":
            status = "warning"
        warnings.append(f"Upper 볼륨 사용률 {report.upper_usage_pct:.0f}% (경고 90%)")

    return InstanceHealth(
        instance_id=instance_id,
        status=status,
        warnings=warnings,
        overlay_mounted=report.overlay_mounted,
        upper_used_bytes=report.upper_used_bytes,
        upper_total_bytes=report.upper_total_bytes,
        upper_usage_pct=report.upper_usage_pct,
        shares=report.shares,
        kernel=report.kernel,
        uptime_seconds=report.uptime_seconds,
        reported_at=report.reported_at,
        checked_at=checked_at,
    )
