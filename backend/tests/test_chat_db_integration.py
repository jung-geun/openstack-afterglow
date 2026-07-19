"""빌트인 AI 채팅 — MariaDB 실 SQL 통합 테스트 (마이그레이션/ORM/쿼리/암호화/쿼터 라운드트립).

로컬에서 AFTERGLOW_TEST_DATABASE_URL 미설정 시 자동 skip, CI 의 test-backend-db 잡에서 실행된다.
실행: AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test \
     pytest tests/test_chat_db_integration.py -v -m db

단위 테스트(mock)가 커버하지 못하는 실 DB 경로를 한 번에 검증:
- ORM DDL(create_all) ↔ 컬럼/타입, provider/model INSERT + UNIQUE
- resolve_model 의 JOIN + api_key 암호화 저장(v3:) → 복호화 왕복
- 대화/메시지 소유권, apply_usage 의 원자적 used_quota UPDATE + 원장 append
- precheck 쿼터 차단
"""

import os
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select, text

import app.models.db  # noqa: F401 — side-effect: Base 에 ORM 모델 등록
from app.models.chat_db import ChatUsageLog, LlmProvider, UserWallet

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"
_KEY_HEX = "a" * 64
_CHAT_TABLES = (
    "chat_usage_logs",
    "chat_messages",
    "chat_conversations",
    "user_wallets",
    "llm_models",
    "llm_providers",
)


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


@pytest_asyncio.fixture
async def chat_db(db_url, monkeypatch):
    """app.database 전역 엔진을 테스트 DB로 초기화하고 chat 테이블을 준비한다.

    provider_store/credit 는 get_session_factory()·get_settings() 를 내부에서 쓰므로,
    암호화 마스터키와 크레딧 설정을 여기서 주입한다.
    """
    from app import database

    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_KEY_HEX),
    )
    monkeypatch.setattr(
        "app.services.chat.credit.get_settings",
        lambda: SimpleNamespace(chat_credit_per_usd=1000.0, chat_default_monthly_quota=100000.0),
    )

    database.init_db(db_url)
    async with database._engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)
    # 이전 실행 잔여 정리
    async with database._engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in _CHAT_TABLES:
            await conn.execute(text(f"DELETE FROM {t}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    yield database

    async with database._engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in _CHAT_TABLES:
            await conn.execute(text(f"DELETE FROM {t}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    await database._engine.dispose()
    database._engine = None
    database._session_factory = None


async def test_provider_model_conversation_usage_roundtrip(chat_db):
    from app.services.chat import conversation_store as cs
    from app.services.chat import credit
    from app.services.chat import provider_store as ps

    factory = chat_db.get_session_factory()

    # 1. 프로바이더 + 모델 (api_key 암호화 저장)
    prov = await ps.create_provider(name="openai", api_base=None, api_key="sk-secret-123", margin_multiplier=1.0)
    assert prov["has_api_key"] is True
    assert "api_key" not in prov  # 응답 마스킹
    await ps.create_model(provider_id=prov["id"], model_name="gpt-4o", display_name="GPT-4o")

    # 2. resolve_model — JOIN + 복호화 왕복
    resolved = await ps.resolve_model("gpt-4o")
    assert resolved is not None
    assert resolved["api_key"] == "sk-secret-123"
    assert resolved["provider_name"] == "openai"

    # 3. 저장 시 ciphertext 는 v3:, 평문 미포함
    async with factory() as s:
        row = (await s.execute(select(LlmProvider).where(LlmProvider.id == prov["id"]))).scalar_one()
        assert row.encrypted_api_key.startswith("v3:")
        assert "sk-secret-123" not in row.encrypted_api_key

    # 4. 미등록 모델 → resolve None (화이트리스트)
    assert await ps.resolve_model("no-such-model") is None

    # 5. 대화/메시지 + 소유권
    conv = await cs.create_conversation(project_id="p1", user_id="u1", title="t", model_name="gpt-4o")
    await cs.add_message(conv["id"], role="user", content="안녕하세요")
    msgs = await cs.list_messages(conv["id"], project_id="p1", user_id="u1")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "안녕하세요"
    with pytest.raises(cs.ConversationForbidden):
        await cs.get_conversation(conv["id"], project_id="other-project", user_id="u1")

    # 6. apply_usage — 원자적 used_quota UPDATE + 원장 append
    credited = await credit.apply_usage(
        user_id="u1",
        project_id="p1",
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        raw_cost=0.002,
        margin_multiplier=1.5,
        conversation_id=conv["id"],
        source="web",
    )
    assert credited == Decimal("3.00000000")  # 0.002 USD × 1.5 × 1000

    async with factory() as s:
        wallet = await s.get(UserWallet, "u1")
        assert wallet.used_quota_this_month == Decimal("3.00000000")
        logs = (await s.execute(select(ChatUsageLog).where(ChatUsageLog.user_id == "u1"))).scalars().all()
        assert len(logs) == 1
        assert logs[0].credited_cost == Decimal("3.00000000")
        assert logs[0].provider == "openai"

    # 7. 두 번째 과금 → 누적(원자적 증가)
    await credit.apply_usage(
        user_id="u1",
        project_id="p1",
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=10,
        raw_cost=0.001,
        margin_multiplier=1.0,
        conversation_id=conv["id"],
        source="web",
    )
    async with factory() as s:
        wallet = await s.get(UserWallet, "u1")
        assert wallet.used_quota_this_month == Decimal("4.00000000")  # 3 + 1

    # 8. 쿼터 상한을 사용량 아래로 낮추면 precheck 차단
    async with factory() as s, s.begin():
        w = await s.get(UserWallet, "u1")
        w.max_quota_monthly = Decimal("1")
    with pytest.raises(credit.QuotaExceeded):
        await credit.precheck("u1", "p1")


async def test_provider_name_unique(chat_db):
    from app.services.chat import provider_store as ps

    await ps.create_provider(name="dup", api_key=None)
    with pytest.raises(ps.ProviderValidationError):
        await ps.create_provider(name="dup", api_key=None)


async def test_conversation_user_scope_cross_project(chat_db):
    """대화 소유는 user_id 기준(프로젝트 무관): 다른 project 로 만든 대화도 같은 user 는 조회, 타 user 는 403."""
    from app.services.chat import conversation_store as cs

    c1 = await cs.create_conversation(project_id="projA", user_id="u1", title="A", model_name="m")
    c2 = await cs.create_conversation(project_id="projB", user_id="u1", title="B", model_name="m")
    await cs.create_conversation(project_id="projA", user_id="u2", title="타인", model_name="m")

    # u1 목록 → 프로젝트 무관하게 본인 대화 2개(타 user 것 제외)
    ids = {c["id"] for c in await cs.list_conversations(user_id="u1")}
    assert c1["id"] in ids and c2["id"] in ids
    assert len(ids) == 2

    # u1 은 projB 대화도 조회 가능(프로젝트 무관)
    assert (await cs.get_conversation(c2["id"], user_id="u1"))["id"] == c2["id"]

    # 타 user 는 소유권 없음 → Forbidden (IDOR 경계)
    with pytest.raises(cs.ConversationForbidden):
        await cs.get_conversation(c1["id"], user_id="u2")
    with pytest.raises(cs.ConversationForbidden):
        await cs.delete_conversation(c1["id"], user_id="u2")


async def test_chat_content_encryption_at_rest(chat_db):
    """메시지 content/tool_calls, 대화 title 이 DB 에 v3: 암호문으로 저장되고 조회 시 평문 복원."""
    from app.models.chat_db import ChatConversation, ChatMessage
    from app.services.chat import conversation_store as cs

    factory = chat_db.get_session_factory()

    conv = await cs.create_conversation(project_id="p1", user_id="u1", title="비밀 제목", model_name="m")
    await cs.add_message(
        conv["id"], role="assistant", content="비밀 응답", tool_calls=[{"id": "c1", "name": "list_instances"}]
    )

    # DB 원시값은 암호문(v3:) — 평문이 컬럼에 노출되지 않아야 한다.
    async with factory() as s:
        row_conv = await s.get(ChatConversation, conv["id"])
        assert row_conv.title.startswith("v3:")
        assert "비밀 제목" not in row_conv.title
        msgs = (await s.execute(select(ChatMessage).where(ChatMessage.conversation_id == conv["id"]))).scalars().all()
        assert msgs[0].content.startswith("v3:")
        assert "비밀 응답" not in msgs[0].content
        assert msgs[0].tool_calls.startswith("v3:")
        assert "list_instances" not in msgs[0].tool_calls

    # 서비스 조회 시 평문 복원
    got = await cs.get_conversation(conv["id"], project_id="p1", user_id="u1")
    assert got["title"] == "비밀 제목"
    out = await cs.list_messages(conv["id"], project_id="p1", user_id="u1")
    assert out[0]["content"] == "비밀 응답"
    assert out[0]["tool_calls"] == [{"id": "c1", "name": "list_instances"}]


async def test_system_charge_does_not_debit_wallet(chat_db):
    """charge_wallet=False(제목 요약 등 시스템 부담)는 usage_logs 만 남기고 지갑 미차감."""
    from app.services.chat import credit

    factory = chat_db.get_session_factory()

    await credit.precheck("sysu", "p1")  # 지갑 생성(used=0)
    await credit.apply_usage(
        user_id="sysu",
        project_id="p1",
        model_name="gpt-4o-mini",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=4,
        raw_cost=0.0001,
        margin_multiplier=1.0,
        source="system",
        charge_wallet=False,
    )
    async with factory() as s:
        wallet = await s.get(UserWallet, "sysu")
        assert wallet.used_quota_this_month == Decimal("0")  # 미차감
        logs = (await s.execute(select(ChatUsageLog).where(ChatUsageLog.user_id == "sysu"))).scalars().all()
        assert len(logs) == 1
        assert logs[0].source == "system"


async def test_set_title_model_single(chat_db):
    """set_title_model 은 최대 1개만 is_title_model=True 로 유지(이동/해제 포함)."""
    from app.services.chat import provider_store as ps

    prov = await ps.create_provider(name="p-title", api_key=None)
    m1 = await ps.create_model(provider_id=prov["id"], model_name="title-a")
    await ps.create_model(provider_id=prov["id"], model_name="title-b")

    await ps.set_title_model(m1["id"])
    resolved = await ps.resolve_title_model()
    assert resolved is not None and resolved["model_name"] == "title-a"

    # 다른 모델로 이동 → 이전 모델은 자동 해제(단일 보장)
    m2 = next(m for m in await ps.list_models() if m["model_name"] == "title-b")
    await ps.set_title_model(m2["id"])
    flags = {m["model_name"]: m["is_title_model"] for m in await ps.list_models()}
    assert flags["title-a"] is False and flags["title-b"] is True

    await ps.set_title_model(None)  # 해제
    assert await ps.resolve_title_model() is None


async def test_stats_aggregation(chat_db):
    """실 DB GROUP BY 집계 — overview/by_model/by_user/monthly + source 규칙(by_user 는 system 제외)."""
    from app.services.chat import credit, stats

    # 사용자 u1(web), u2(web) + system 부담 1건을 원장에 적재
    async def log(user, model, pt, ct, raw, source="web"):
        await credit.apply_usage(
            user_id=user,
            project_id="p1",
            model_name=model,
            provider="openai",
            prompt_tokens=pt,
            completion_tokens=ct,
            raw_cost=raw,
            margin_multiplier=1.0,
            conversation_id=f"conv-{user}",
            source=source,
            charge_wallet=(source != "system"),
        )

    await log("u1", "gpt-4o", 100, 50, 0.002)
    await log("u1", "gpt-4o-mini", 20, 10, 0.0001)
    await log("u2", "gpt-4o", 200, 100, 0.004)
    await log("sys", "gpt-4o-mini", 5, 5, 0.00001, source="system")

    ov = await stats.overview("all", "p1")
    assert ov["prompt_tokens"] == 325 and ov["completion_tokens"] == 165  # system 포함
    assert ov["request_count"] == 4
    assert ov["active_users"] == 3  # u1, u2, sys
    src = {r["source"]: r for r in ov["by_source"]}
    assert src["system"]["request_count"] == 1

    models = {m["model_name"]: m for m in await stats.by_model("all", "p1")}
    assert models["gpt-4o"]["total_tokens"] == 450  # (100+50)+(200+100)
    assert models["gpt-4o"]["request_count"] == 2

    users = {u["user_id"]: u for u in await stats.by_user("all", "p1")}
    assert "sys" not in users  # by_user 는 system 제외
    assert users["u2"]["total_tokens"] == 300
    # 토큰 desc 정렬 — u2(300) 가 u1(180) 앞
    ordered = [u["user_id"] for u in await stats.by_user("all", "p1")]
    assert ordered[0] == "u2"

    months = await stats.monthly("all", "p1")
    assert len(months) >= 1
    assert all("month" in m and "ts" in m for m in months)
    assert sum(m["total_tokens"] for m in months) == 490  # 전체 토큰 합

    assert "p1" in await stats.projects_with_usage("all")
