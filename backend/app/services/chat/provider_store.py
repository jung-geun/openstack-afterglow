"""빌트인 AI 채팅 프로바이더/모델 설정 저장소 (MySQL).

관리자가 등록한 LLM 프로바이더/모델을 CRUD 하고, 완료 경로가 model_name 으로
api_base/복호화 키를 해석(resolve_model)한다.

⚠️ api_key 는 절대 API 응답/로그에 노출하지 않는다: 공개 dict(_provider_public)는
has_api_key 불리언만 반환하고, 복호화 평문은 resolve_model 이 서버 내부 완료 경로에만 반환한다.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import LlmModel, LlmProvider
from app.services.k3s_crypto import decrypt_llm_provider_key, encrypt_llm_provider_key

logger = logging.getLogger(__name__)


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — fail-closed(503)."""


class ProviderNotFoundError(LookupError):
    """프로바이더/모델 미존재 — 404."""


class ProviderValidationError(ValueError):
    """입력 검증 실패/제약 위반 — 400."""


def _require_db():
    if not is_db_available():
        raise ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 가 구성되지 않았습니다")
    return factory


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _to_decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ProviderValidationError(f"{field} 값이 올바르지 않습니다") from exc


def _provider_public(row: LlmProvider) -> dict:
    """관리자 응답용 공개 dict — api_key 평문/암호문 절대 미포함."""
    return {
        "id": row.id,
        "name": row.name,
        "api_base": row.api_base,
        "has_api_key": bool(row.encrypted_api_key),
        "is_active": row.is_active,
        "margin_multiplier": float(row.margin_multiplier),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _model_public(row: LlmModel) -> dict:
    return {
        "id": row.id,
        "provider_id": row.provider_id,
        "model_name": row.model_name,
        "display_name": row.display_name,
        "is_active": row.is_active,
        "input_price": float(row.input_price) if row.input_price is not None else None,
        "output_price": float(row.output_price) if row.output_price is not None else None,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# ---------------------------------------------------------------------------
# 프로바이더 CRUD
# ---------------------------------------------------------------------------
async def create_provider(
    *,
    name: str,
    api_base: str | None = None,
    api_key: str | None = None,
    margin_multiplier=1.0,
    is_active: bool = True,
) -> dict:
    factory = _require_db()
    if not name or not name.strip():
        raise ProviderValidationError("name 은 필수입니다")
    row = LlmProvider(
        name=name.strip(),
        api_base=(api_base or None),
        encrypted_api_key=(encrypt_llm_provider_key(api_key) if api_key else None),
        margin_multiplier=_to_decimal(margin_multiplier, "margin_multiplier"),
        is_active=is_active,
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _provider_public(row)
    except IntegrityError as exc:
        raise ProviderValidationError(f"이미 존재하는 프로바이더 이름입니다: {name}") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_providers() -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (await session.execute(select(LlmProvider).order_by(LlmProvider.id))).scalars().all()
            return [_provider_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_provider(provider_id: int, patch: dict) -> dict:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await session.get(LlmProvider, provider_id)
            if row is None:
                raise ProviderNotFoundError(f"프로바이더 {provider_id} 를 찾을 수 없습니다")
            if patch.get("name"):
                row.name = str(patch["name"]).strip()
            if "api_base" in patch:
                row.api_base = patch["api_base"] or None
            if "api_key" in patch:
                row.encrypted_api_key = encrypt_llm_provider_key(patch["api_key"]) if patch["api_key"] else None
            if patch.get("margin_multiplier") is not None:
                row.margin_multiplier = _to_decimal(patch["margin_multiplier"], "margin_multiplier")
            if patch.get("is_active") is not None:
                row.is_active = bool(patch["is_active"])
            await session.flush()
            return _provider_public(row)
    except IntegrityError as exc:
        raise ProviderValidationError("프로바이더 이름이 중복됩니다") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_provider(provider_id: int) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await session.get(LlmProvider, provider_id)
            if row is None:
                raise ProviderNotFoundError(f"프로바이더 {provider_id} 를 찾을 수 없습니다")
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


# ---------------------------------------------------------------------------
# 모델 CRUD
# ---------------------------------------------------------------------------
async def create_model(
    *,
    provider_id: int,
    model_name: str,
    display_name: str | None = None,
    input_price=None,
    output_price=None,
    is_active: bool = True,
) -> dict:
    factory = _require_db()
    if not model_name or not model_name.strip():
        raise ProviderValidationError("model_name 은 필수입니다")
    row = LlmModel(
        provider_id=provider_id,
        model_name=model_name.strip(),
        display_name=(display_name or None),
        input_price=(_to_decimal(input_price, "input_price") if input_price is not None else None),
        output_price=(_to_decimal(output_price, "output_price") if output_price is not None else None),
        is_active=is_active,
    )
    try:
        async with factory() as session, session.begin():
            # provider 존재 검증 (FK 위반 → 명확한 400)
            provider = await session.get(LlmProvider, provider_id)
            if provider is None:
                raise ProviderValidationError(f"프로바이더 {provider_id} 가 존재하지 않습니다")
            session.add(row)
            await session.flush()
            return _model_public(row)
    except IntegrityError as exc:
        raise ProviderValidationError("프로바이더 내 model_name 이 중복됩니다") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_models(*, active_only: bool = False) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = select(LlmModel).order_by(LlmModel.id)
            if active_only:
                stmt = stmt.where(LlmModel.is_active.is_(True))
            rows = (await session.execute(stmt)).scalars().all()
            return [_model_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_model(model_id: int, patch: dict) -> dict:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await session.get(LlmModel, model_id)
            if row is None:
                raise ProviderNotFoundError(f"모델 {model_id} 를 찾을 수 없습니다")
            if patch.get("model_name"):
                row.model_name = str(patch["model_name"]).strip()
            if "display_name" in patch:
                row.display_name = patch["display_name"] or None
            if "input_price" in patch:
                row.input_price = (
                    _to_decimal(patch["input_price"], "input_price") if patch["input_price"] is not None else None
                )
            if "output_price" in patch:
                row.output_price = (
                    _to_decimal(patch["output_price"], "output_price") if patch["output_price"] is not None else None
                )
            if patch.get("is_active") is not None:
                row.is_active = bool(patch["is_active"])
            await session.flush()
            return _model_public(row)
    except IntegrityError as exc:
        raise ProviderValidationError("프로바이더 내 model_name 이 중복됩니다") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_model(model_id: int) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await session.get(LlmModel, model_id)
            if row is None:
                raise ProviderNotFoundError(f"모델 {model_id} 를 찾을 수 없습니다")
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


# ---------------------------------------------------------------------------
# 완료 경로용 해석 (서버 내부 전용)
# ---------------------------------------------------------------------------
async def resolve_model(model_name: str) -> dict | None:
    """활성 model_name → 완료 호출에 필요한 설정. 미존재/비활성 시 None(화이트리스트 역할).

    ⚠️ 반환 dict 의 api_key 는 복호화 평문이다 — API 응답/로그에 절대 노출 금지.
    """
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = (
                select(LlmModel, LlmProvider)
                .join(LlmProvider, LlmModel.provider_id == LlmProvider.id)
                .where(
                    LlmModel.model_name == model_name,
                    LlmModel.is_active.is_(True),
                    LlmProvider.is_active.is_(True),
                )
            )
            res = (await session.execute(stmt)).first()
            if res is None:
                return None
            model, provider = res
            api_key = decrypt_llm_provider_key(provider.encrypted_api_key) if provider.encrypted_api_key else None
            return {
                "model_name": model.model_name,
                "provider_name": provider.name,
                "api_base": provider.api_base,
                "api_key": api_key,
                "margin_multiplier": float(provider.margin_multiplier),
                "input_price": float(model.input_price) if model.input_price is not None else None,
                "output_price": float(model.output_price) if model.output_price is not None else None,
            }
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
