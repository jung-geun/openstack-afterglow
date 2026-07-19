"""빌트인 AI 채팅 크레딧/쿼터 관리 (MySQL user_wallets + chat_usage_logs).

과금 모델: 모델별 raw_cost(USD) × margin_multiplier × credit_per_usd = credited_cost(크레딧).
월간 쿼터 상한(used_quota_this_month ≥ max_quota_monthly)을 초과하면 요청을 차단한다.

⚠️ 보안/정합성:
- precheck 는 **fail-closed**: DB 장애 시 요청 거부(ChatStorageUnavailable → 503).
- apply_usage 는 **원자적 SQL UPDATE**(used_quota += credited)로 동시요청 race 를 완화한다.
- pre-check ↔ apply_usage 사이 TOCTOU 로 소폭 초과는 허용(하드락 미도입) — 내부 쿼터 용도.
- 스트리밍 중단 시에도 호출부가 finally 에서 apply_usage 를 호출해 부분 사용량을 과금한다.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatUsageLog, UserWallet

logger = logging.getLogger(__name__)

_CREDIT_QUANTUM = Decimal("0.00000001")  # DECIMAL(18,8)


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — fail-closed(503)."""


class QuotaExceeded(RuntimeError):
    """월 쿼터 초과 — 402."""


def _require_db():
    if not is_db_available():
        raise ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 가 구성되지 않았습니다")
    return factory


def credits_for_cost(raw_cost_usd, margin_multiplier=1.0, credit_per_usd=None) -> Decimal:
    """raw_cost(USD) → 차감 크레딧. 순수 함수(테스트 용이).

    credited = raw_cost × margin_multiplier × credit_per_usd, 8자리로 양자화.
    """
    if credit_per_usd is None:
        credit_per_usd = get_settings().chat_credit_per_usd
    value = Decimal(str(raw_cost_usd)) * Decimal(str(margin_multiplier)) * Decimal(str(credit_per_usd))
    if value < 0:
        value = Decimal("0")
    return value.quantize(_CREDIT_QUANTUM)


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _maybe_reset_month(wallet: UserWallet) -> None:
    """새 달이면 used_quota_this_month 를 0으로 리셋(스케줄러 미가동 시 lazy 보정)."""
    today = datetime.now(UTC).date()
    period = wallet.quota_period_start
    if period is None or (period.year, period.month) != (today.year, today.month):
        wallet.used_quota_this_month = Decimal("0")
        wallet.quota_period_start = _first_of_month(today)


async def _get_or_create_wallet(session, user_id: str, project_id: str | None) -> UserWallet:
    wallet = await session.get(UserWallet, user_id)
    if wallet is None:
        default_quota = Decimal(str(get_settings().chat_default_monthly_quota))
        wallet = UserWallet(
            user_id=user_id,
            project_id=project_id,
            max_quota_monthly=default_quota,
            used_quota_this_month=Decimal("0"),
            quota_period_start=_first_of_month(datetime.now(UTC).date()),
        )
        session.add(wallet)
        await session.flush()
    return wallet


async def precheck(user_id: str, project_id: str | None = None) -> None:
    """월 쿼터 초과 시 QuotaExceeded. DB 장애 시 ChatStorageUnavailable(fail-closed).

    max_quota_monthly == 0 은 '무제한'으로 해석(설정 default_monthly_quota=0 대응).
    """
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            wallet = await _get_or_create_wallet(session, user_id, project_id)
            _maybe_reset_month(wallet)
            if not wallet.is_active:
                raise QuotaExceeded("비활성 지갑입니다")
            if (
                wallet.max_quota_monthly
                and wallet.max_quota_monthly > 0
                and wallet.used_quota_this_month >= wallet.max_quota_monthly
            ):
                raise QuotaExceeded("월 사용 한도를 초과했습니다")
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def apply_usage(
    *,
    user_id: str,
    project_id: str,
    model_name: str,
    provider: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    raw_cost,
    margin_multiplier=1.0,
    conversation_id: str | None = None,
    source: str = "web",
    api_key_id: int | None = None,
    charge_wallet: bool = True,
) -> Decimal:
    """사용량을 원장에 기록하고 지갑 used_quota 를 원자적으로 증가. 차감 크레딧 반환.

    호출부는 스트리밍 완료/중단(finally) 시점에 반드시 1회 호출한다.

    charge_wallet=False: 지갑 차감 없이 usage_logs 만 기록(제목 요약 등 시스템 부담 호출).
    이때도 credited_cost 는 산출해 원장에 남겨 시스템 원가를 추적한다(source="system").
    """
    credited = credits_for_cost(raw_cost, margin_multiplier)
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            if charge_wallet:
                # 지갑이 없으면 생성(+월 리셋 보정)
                wallet = await _get_or_create_wallet(session, user_id, project_id)
                _maybe_reset_month(wallet)
                # 원자적 차감 — 컬럼 self-reference UPDATE(동시요청 race 완화)
                await session.execute(
                    update(UserWallet)
                    .where(UserWallet.user_id == user_id)
                    .values(used_quota_this_month=UserWallet.used_quota_this_month + credited)
                )
            session.add(
                ChatUsageLog(
                    project_id=project_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    model_name=model_name,
                    provider=provider,
                    prompt_tokens=int(prompt_tokens),
                    completion_tokens=int(completion_tokens),
                    raw_cost=Decimal(str(raw_cost)),
                    credited_cost=credited,
                    source=source,
                    api_key_id=api_key_id,
                )
            )
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
    return credited
