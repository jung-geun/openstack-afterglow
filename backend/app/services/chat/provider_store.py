"""빌트인 AI 채팅 프로바이더/모델 설정 저장소 (MySQL).

관리자가 등록한 LLM 프로바이더/모델을 CRUD 하고, 완료 경로가 model_name 으로
api_base/복호화 키를 해석(resolve_model)한다.

⚠️ api_key 는 절대 API 응답/로그에 노출하지 않는다: 공개 dict(_provider_public)는
has_api_key 불리언만 반환하고, 복호화 평문은 resolve_model 이 서버 내부 완료 경로에만 반환한다.
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import LlmModel, LlmProvider
from app.services.chat.litellm_client import effective_prices_per_million
from app.services.chat.models_dev import ModelsDevCatalog
from app.services.k3s_crypto import decrypt_llm_provider_key, encrypt_llm_provider_key

logger = logging.getLogger(__name__)

_PER_TOKEN_QUANTUM = Decimal("0.0000000001")
_TOKENS_PER_MILLION = Decimal("1000000")


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — fail-closed(503)."""


class ProviderNotFoundError(LookupError):
    """프로바이더/모델 미존재 — 404."""


class ModelsDevImportConflictError(RuntimeError):
    """models.dev provider mapping would orphan imported local prices."""


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
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ProviderValidationError(f"{field} 값이 올바르지 않습니다") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ProviderValidationError(f"{field} 값은 유한한 0 이상의 숫자여야 합니다")
    return parsed


def _per_token_price(value, field: str) -> Decimal | None:
    if value is None:
        return None
    per_million = _to_decimal(value, field)
    per_token = (per_million / _TOKENS_PER_MILLION).quantize(_PER_TOKEN_QUANTUM, rounding=ROUND_HALF_UP)
    if per_million != 0 and per_token == 0:
        raise ProviderValidationError(f"{field} 값이 저장 정밀도보다 작습니다")
    return per_token


def _validate_price_pair(input_price_per_million, output_price_per_million) -> tuple[Decimal | None, Decimal | None]:
    if (input_price_per_million is None) != (output_price_per_million is None):
        raise ProviderValidationError("입력·출력 가격은 함께 설정하거나 함께 비워야 합니다")
    return (
        _per_token_price(input_price_per_million, "input_price_per_million"),
        _per_token_price(output_price_per_million, "output_price_per_million"),
    )


def _per_million_price(value: Decimal | None) -> Decimal | None:
    return value * _TOKENS_PER_MILLION if value is not None else None


def _json_decimal_strings(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_decimal_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_decimal_strings(item) for item in value]
    return value


def _provider_public(row: LlmProvider) -> dict:
    """관리자 응답용 공개 dict — api_key 평문/암호문 절대 미포함."""
    return {
        "id": row.id,
        "name": row.name,
        "provider_type": row.provider_type,
        "api_base": row.api_base,
        "has_api_key": bool(row.encrypted_api_key),
        "is_active": row.is_active,
        "margin_multiplier": float(row.margin_multiplier),
        "models_dev_provider_id": row.models_dev_provider_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _litellm_capabilities(model_name: str, provider_type: str | None) -> dict:
    """litellm 런타임 능력 판별(저장 override/import 없을 때 fallback). 각 조회는 fail-safe False."""

    def _safe(fn_name: str) -> bool:
        try:
            import litellm

            return bool(getattr(litellm, fn_name)(model=model_name))
        except Exception:
            return False

    vision = _safe("supports_vision")
    return {
        "vision": vision,
        "reasoning": _safe("supports_reasoning"),
        "tool_call": _safe("supports_function_calling"),
        "attachment": vision,  # 이미지 첨부 ≈ vision (litellm은 별도 플래그 없음)
        "modalities": None,  # litellm은 modality 목록을 주지 않음 — models.dev import 로 채움
        "reasoning_options": [],
        "context_limit": None,
    }


def _effective_capabilities(row: LlmModel, provider_type: str | None) -> tuple[dict, str]:
    """저장 능력(override/models_dev) 우선, 없으면 litellm 런타임. (capabilities, source) 반환."""
    if row.capabilities:
        return row.capabilities, (row.capability_source or "override")
    return _litellm_capabilities(row.model_name, provider_type), "litellm"


def _model_public(
    row: LlmModel,
    *,
    effective_input_price_per_million: Decimal | None = None,
    effective_output_price_per_million: Decimal | None = None,
    effective_price_source: str | None = None,
    provider_type: str | None = None,
) -> dict:
    eff_caps, eff_caps_source = _effective_capabilities(row, provider_type)
    return {
        "id": row.id,
        "provider_id": row.provider_id,
        "model_name": row.model_name,
        "display_name": row.display_name,
        "is_active": row.is_active,
        "is_title_model": row.is_title_model,
        "is_memory_model": row.is_memory_model,
        "input_price_per_million": _per_million_price(row.input_price),
        "output_price_per_million": _per_million_price(row.output_price),
        "effective_input_price_per_million": effective_input_price_per_million,
        "effective_output_price_per_million": effective_output_price_per_million,
        "effective_price_source": effective_price_source,
        "models_dev_model_id": row.models_dev_model_id,
        "price_source": row.price_source,
        # 능력: 저장(override) + 유효(effective) 를 함께 노출(가격과 동일 패턴)
        "capabilities": row.capabilities,
        "capability_source": row.capability_source,
        "effective_capabilities": eff_caps,
        "effective_capability_source": eff_caps_source,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# ---------------------------------------------------------------------------
# 프로바이더 CRUD
# ---------------------------------------------------------------------------
async def create_provider(
    *,
    name: str,
    provider_type: str = "openai",
    api_base: str | None = None,
    api_key: str | None = None,
    margin_multiplier=1.0,
    models_dev_provider_id: str | None = None,
    is_active: bool = True,
) -> dict:
    factory = _require_db()
    if not name or not name.strip():
        raise ProviderValidationError("name 은 필수입니다")
    row = LlmProvider(
        name=name.strip(),
        provider_type=(provider_type or "openai").strip(),
        api_base=(api_base or None),
        encrypted_api_key=(encrypt_llm_provider_key(api_key) if api_key else None),
        margin_multiplier=_to_decimal(margin_multiplier, "margin_multiplier"),
        models_dev_provider_id=(models_dev_provider_id or None),
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
            if patch.get("provider_type"):
                row.provider_type = str(patch["provider_type"]).strip()
            if "api_base" in patch:
                row.api_base = patch["api_base"] or None
            if "api_key" in patch:
                row.encrypted_api_key = encrypt_llm_provider_key(patch["api_key"]) if patch["api_key"] else None
            if patch.get("margin_multiplier") is not None:
                row.margin_multiplier = _to_decimal(patch["margin_multiplier"], "margin_multiplier")
            if "models_dev_provider_id" in patch:
                row.models_dev_provider_id = patch["models_dev_provider_id"] or None
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
    input_price_per_million=None,
    output_price_per_million=None,
    capabilities: dict | None = None,
    is_active: bool = True,
) -> dict:
    factory = _require_db()
    if not model_name or not model_name.strip():
        raise ProviderValidationError("model_name 은 필수입니다")
    input_price, output_price = _validate_price_pair(input_price_per_million, output_price_per_million)
    row = LlmModel(
        provider_id=provider_id,
        model_name=model_name.strip(),
        display_name=(display_name or None),
        input_price=input_price,
        output_price=output_price,
        price_source="manual" if input_price is not None else None,
        capabilities=(capabilities or None),
        capability_source=("override" if capabilities else None),
        is_active=is_active,
    )
    try:
        async with factory() as session, session.begin():
            provider = await session.get(LlmProvider, provider_id)
            if provider is None:
                raise ProviderValidationError(f"프로바이더 {provider_id} 가 존재하지 않습니다")
            session.add(row)
            await session.flush()
            return _model_public(row, provider_type=provider.provider_type)
    except IntegrityError as exc:
        raise ProviderValidationError("프로바이더 내 model_name 이 중복됩니다") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_models(*, active_only: bool = False) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = (
                select(LlmModel, LlmProvider)
                .join(LlmProvider, LlmProvider.id == LlmModel.provider_id)
                .order_by(LlmModel.id)
            )
            if active_only:
                stmt = stmt.where(LlmModel.is_active.is_(True))
            rows = (await session.execute(stmt)).all()
            public_models: list[dict] = []
            for model, provider in rows:
                stored_input = _per_million_price(model.input_price)
                stored_output = _per_million_price(model.output_price)
                fallback_input, fallback_output = (
                    (None, None)
                    if stored_input is not None and stored_output is not None
                    else effective_prices_per_million(model.model_name, provider.provider_type)
                )
                effective_input = stored_input if stored_input is not None else fallback_input
                effective_output = stored_output if stored_output is not None else fallback_output
                if stored_input is not None and stored_output is not None:
                    effective_source = model.price_source
                elif effective_input is not None and effective_output is not None:
                    effective_source = "litellm" if stored_input is None and stored_output is None else "partial"
                else:
                    effective_source = "unpriced"
                public_models.append(
                    _model_public(
                        model,
                        effective_input_price_per_million=effective_input,
                        effective_output_price_per_million=effective_output,
                        effective_price_source=effective_source,
                        provider_type=provider.provider_type,
                    )
                )
            return public_models
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_model(model_id: int, patch: dict) -> dict:
    factory = _require_db()
    has_input_price = "input_price_per_million" in patch
    has_output_price = "output_price_per_million" in patch
    if has_input_price != has_output_price:
        raise ProviderValidationError("입력·출력 가격은 함께 설정하거나 함께 비워야 합니다")
    try:
        async with factory() as session, session.begin():
            row = await session.get(LlmModel, model_id)
            if row is None:
                raise ProviderNotFoundError(f"모델 {model_id} 를 찾을 수 없습니다")
            if patch.get("model_name"):
                row.model_name = str(patch["model_name"]).strip()
            if "display_name" in patch:
                row.display_name = patch["display_name"] or None
            if has_input_price:
                input_price, output_price = _validate_price_pair(
                    patch["input_price_per_million"], patch["output_price_per_million"]
                )
                row.input_price = input_price
                row.output_price = output_price
                row.price_source = "manual" if input_price is not None else None
                row.price_metadata = None
            if "capabilities" in patch:
                # 관리자 수동 오버라이드 — models.dev import 로 덮이지 않도록 source=override 고정.
                row.capabilities = patch["capabilities"] or None
                row.capability_source = "override" if patch["capabilities"] else None
            if patch.get("is_active") is not None:
                row.is_active = bool(patch["is_active"])
            await session.flush()
            provider = await session.get(LlmProvider, row.provider_id)
            return _model_public(row, provider_type=provider.provider_type if provider else None)
    except IntegrityError as exc:
        raise ProviderValidationError("프로바이더 내 model_name 이 중복됩니다") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def import_models_dev_prices(
    *,
    local_provider_id: int,
    models_dev_provider_id: str,
    selections: list[dict[str, object]],
    catalog: ModelsDevCatalog,
) -> list[dict]:
    """Atomically apply administrator-selected exact models.dev price pairs."""
    if not 1 <= len(selections) <= 500:
        raise ProviderValidationError("selections는 1개 이상 500개 이하여야 합니다")
    external_provider = catalog.providers.get(models_dev_provider_id)
    if external_provider is None:
        raise ProviderValidationError("models.dev provider를 찾을 수 없습니다")

    selected_external: dict[int, str] = {}
    for selection in selections:
        local_model_id = selection.get("local_model_id")
        external_model_id = selection.get("models_dev_model_id")
        if not isinstance(local_model_id, int) or not isinstance(external_model_id, str) or not external_model_id:
            raise ProviderValidationError("models.dev import selection 형식이 올바르지 않습니다")
        if local_model_id in selected_external:
            raise ProviderValidationError("같은 local_model_id를 중복 선택할 수 없습니다")
        external_model = external_provider.models.get(external_model_id)
        if external_model is None or not external_model.price_available:
            raise ProviderValidationError("선택한 models.dev 모델에 완전한 input/output 가격이 없습니다")
        selected_external[local_model_id] = external_model_id

    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            provider = await session.get(LlmProvider, local_provider_id)
            if provider is None:
                raise ProviderNotFoundError(f"프로바이더 {local_provider_id} 를 찾을 수 없습니다")
            local_models = (
                (await session.execute(select(LlmModel).where(LlmModel.id.in_(selected_external)))).scalars().all()
            )
            if len(local_models) != len(selected_external) or any(
                model.provider_id != local_provider_id for model in local_models
            ):
                raise ProviderValidationError("선택한 local model이 프로바이더에 속하지 않습니다")
            if any(model.price_source == "manual" for model in local_models):
                raise ModelsDevImportConflictError("수동 확정 가격 모델은 models.dev import로 덮어쓸 수 없습니다")

            if provider.models_dev_provider_id and provider.models_dev_provider_id != models_dev_provider_id:
                existing_imports = (
                    (
                        await session.execute(
                            select(LlmModel.id).where(
                                LlmModel.provider_id == local_provider_id,
                                LlmModel.price_source == "models.dev",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                if set(existing_imports) - set(selected_external):
                    raise ModelsDevImportConflictError(
                        "다른 models.dev provider로 변경하려면 기존 imported model을 모두 선택해야 합니다"
                    )
                provider_models = (
                    (await session.execute(select(LlmModel).where(LlmModel.provider_id == local_provider_id)))
                    .scalars()
                    .all()
                )
                for model in provider_models:
                    if model.id not in selected_external and model.price_source != "models.dev":
                        model.models_dev_model_id = None

            provider.models_dev_provider_id = models_dev_provider_id
            rows_by_id = {model.id: model for model in local_models}
            for local_model_id, external_model_id in selected_external.items():
                external_model = external_provider.models[external_model_id]
                row = rows_by_id[local_model_id]
                row.models_dev_model_id = external_model_id
                row.input_price = _per_token_price(external_model.input_price_per_million, "input_price_per_million")
                row.output_price = _per_token_price(external_model.output_price_per_million, "output_price_per_million")
                row.price_source = "models.dev"
                # 능력 import — 관리자 override 는 보존, 아니면 models.dev 능력으로 갱신.
                if row.capability_source != "override" and external_model.capabilities is not None:
                    row.capabilities = external_model.capabilities
                    row.capability_source = "models_dev"
                row.price_metadata = {
                    "source_url": catalog.source_url,
                    "fetched_at": catalog.fetched_at,
                    "last_updated": external_model.last_updated,
                    "cost": _json_decimal_strings(external_model.cost),
                    "unsupported_price_fields": external_model.unsupported_price_fields,
                }
            await session.flush()
            return [
                _model_public(rows_by_id[local_model_id], provider_type=provider.provider_type)
                for local_model_id in selected_external
            ]
    except IntegrityError as exc:
        raise ModelsDevImportConflictError("models.dev 가격 import 저장 충돌") from exc
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


def _resolved_model(model: LlmModel, provider: LlmProvider) -> dict:
    api_key = decrypt_llm_provider_key(provider.encrypted_api_key) if provider.encrypted_api_key else None
    return {
        "model_name": model.model_name,
        "provider_name": provider.name,
        "provider_type": provider.provider_type,
        "api_base": provider.api_base,
        "api_key": api_key,
        "margin_multiplier": Decimal(provider.margin_multiplier),
        "input_price_per_token": Decimal(model.input_price) if model.input_price is not None else None,
        "output_price_per_token": Decimal(model.output_price) if model.output_price is not None else None,
        "price_source": model.price_source,
        # 유효 능력(저장 override/import 우선, 없으면 litellm) — completions 의 vision/tool/effort 게이팅용.
        "capabilities": _effective_capabilities(model, provider.provider_type)[0],
    }


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
            return _resolved_model(model, provider)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def set_title_model(model_id: int | None) -> None:
    """대화 제목 자동 요약에 쓸 모델 1개를 지정. 앱 레벨에서 최대 1개만 True 로 유지.

    model_id=None 이면 지정 해제(모두 False). 대상이 없으면 ProviderNotFoundError.
    """
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            if model_id is not None:
                target = await session.get(LlmModel, model_id)
                if target is None:
                    raise ProviderNotFoundError(f"모델 {model_id} 를 찾을 수 없습니다")
            # 먼저 전부 해제 후 대상만 True (단일 보장)
            await session.execute(update(LlmModel).values(is_title_model=False))
            if model_id is not None:
                await session.execute(update(LlmModel).where(LlmModel.id == model_id).values(is_title_model=True))
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def resolve_title_model() -> dict | None:
    """제목 요약용 모델(is_title_model=True, 활성 + 프로바이더 활성)의 완료 설정. 미지정 시 None.

    ⚠️ 반환 dict 의 api_key 는 복호화 평문 — 서버 내부 요약 호출 전용, 노출 금지.
    """
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = (
                select(LlmModel, LlmProvider)
                .join(LlmProvider, LlmModel.provider_id == LlmProvider.id)
                .where(
                    LlmModel.is_title_model.is_(True),
                    LlmModel.is_active.is_(True),
                    LlmProvider.is_active.is_(True),
                )
                .limit(1)
            )
            res = (await session.execute(stmt)).first()
            if res is None:
                return None
            model, provider = res
            return _resolved_model(model, provider)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def get_provider_for_discovery(provider_id: int) -> dict | None:
    """모델 discovery 용 — provider_type/api_base/복호화 api_key. 미존재 시 None.

    ⚠️ 반환 api_key 는 복호화 평문 — 서버 내부 discovery 호출 전용, API 응답 노출 금지.
    """
    factory = _require_db()
    try:
        async with factory() as session:
            row = await session.get(LlmProvider, provider_id)
            if row is None:
                return None
            api_key = decrypt_llm_provider_key(row.encrypted_api_key) if row.encrypted_api_key else None
            return {"provider_type": row.provider_type, "api_base": row.api_base, "api_key": api_key}
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
