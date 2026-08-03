"""빌트인 AI 채팅 — MariaDB 실 SQL 통합 테스트 (마이그레이션/ORM/쿼리/암호화/쿼터 라운드트립).

로컬에서 AFTERGLOW_TEST_DATABASE_URL 미설정 시 자동 skip, CI 의 test-backend-db 잡에서 실행된다.
실행: AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_pytest \
     AFTERGLOW_TEST_CHECKPOINTER_POSTGRES_URL=postgresql://afterglow:dev@127.0.0.1:5433/afterglow_checkpoints \
     pytest tests/test_chat_db_integration.py -v -m db

단위 테스트(mock)가 커버하지 못하는 실 DB 경로를 한 번에 검증:
- ORM DDL(create_all) ↔ 컬럼/타입, provider/model INSERT + UNIQUE
- resolve_model 의 JOIN + api_key 암호화 저장(v3:) → 복호화 왕복
- 대화/메시지 소유권, apply_usage 의 원자적 used_quota UPDATE + 원장 append
- precheck 쿼터 차단
"""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Event
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select, text

import app.models.db  # noqa: F401 — side-effect: Base 에 ORM 모델 등록
from app.models.chat_db import (
    ChatMcpOAuthRequest,
    ChatMcpServer,
    ChatUsageLog,
    LlmProvider,
    McpDelegatedGrant,
    McpLumenSelection,
    McpOAuthAuthorizationRequest,
    McpOAuthClient,
    McpOAuthCode,
    McpOAuthToken,
    McpOAuthTokenFamily,
    McpOwnerLock,
    McpToolInvocation,
    UserWallet,
)
from app.models.chat_runs import ChatRun
from app.services.chat.litellm_client import UsageCost
from app.services.mcp_control_plane.cleanup import sweep_delegated_authority

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"
_KEY_HEX = "a" * 64


def _usage_cost(raw: Decimal) -> UsageCost:
    return UsageCost(
        raw_cost=raw,
        input_cost=raw,
        output_cost=Decimal("0"),
        pricing_status="priced",
        pricing_snapshot={"model": "test"},
    )


_CHAT_TABLES = (
    "chat_run_segments",
    "chat_run_turns",
    "chat_run_interactions",
    "chat_tool_approvals",
    "chat_run_events",
    "chat_run_providers",
    "chat_runs",
    "chat_temp_threads",
    "chat_api_keys",
    "chat_usage_logs",
    "resource_policies",
    "chat_memory_provenance",
    "chat_memory_outbox",
    "chat_messages",
    "chat_conversations",
    "chat_agents",
    "chat_workspaces",
    "chat_mcp_oauth_connections",
    "chat_mcp_oauth_requests",
    "chat_mcp_servers",
    "chat_memories",
    "user_wallets",
    "llm_models",
    "llm_providers",
    "mcp_oauth_tokens",
    "mcp_oauth_token_families",
    "mcp_oauth_codes",
    "mcp_oauth_authorization_requests",
    "mcp_oauth_clients",
    "mcp_lumen_selections",
    "mcp_personal_tokens",
    "mcp_delegated_grants",
    "mcp_owner_locks",
    "mcp_tool_invocations",
    "activity_logs",
)


@pytest_asyncio.fixture
async def execution_snapshots(chat_db):
    """Immutable executor route snapshots backed by real provider/model rows."""
    from app.services.chat import provider_store as ps

    provider = await ps.create_provider(name="executor-provider", api_key="executor-secret")
    await ps.create_model(
        provider_id=provider["id"],
        model_name="m",
        input_price_per_million=1,
        output_price_per_million=2,
    )
    resolved = await ps.resolve_model("m")
    assert resolved is not None
    return (
        {
            "effective_features": {},
            "provider_id": resolved["provider_id"],
            "model_id": resolved["model_id"],
            "provider_name": resolved["provider_name"],
            "model_name": resolved["model_name"],
            "config_version_hash": resolved["config_version_hash"],
            "capabilities": resolved["capabilities"],
        },
        {
            "input_price_per_token": str(resolved["input_price_per_token"]),
            "output_price_per_token": str(resolved["output_price_per_token"]),
            "component_prices": {},
            "price_source": resolved["price_source"],
            "provider_name": resolved["provider_name"],
            "model_name": resolved["model_name"],
            "margin_multiplier": str(resolved["margin_multiplier"]),
            "chat_credit_per_usd": "1000",
            "rounding_version": "half_even_v1",
        },
    )


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


@pytest_asyncio.fixture
async def chat_checkpointer_db(chat_db):
    """Start the real PostgreSQL checkpointer for v2 durable-run tests."""
    url = os.environ.get("AFTERGLOW_TEST_CHECKPOINTER_POSTGRES_URL")
    if not url:
        pytest.skip("AFTERGLOW_TEST_CHECKPOINTER_POSTGRES_URL 미설정 — v2 checkpointer 테스트 건너뜀")

    from app.services.chat.checkpointer import chat_checkpointer

    if not await chat_checkpointer.start(url):
        pytest.fail("PostgreSQL checkpointer could not be initialized")
    try:
        yield chat_checkpointer
    finally:
        await chat_checkpointer.close()


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
    database._db_unhealthy_until = 0.0
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
    model = await ps.create_model(provider_id=prov["id"], model_name="gpt-4o", display_name="GPT-4o")

    # 2. resolve_model — JOIN + 복호화 왕복
    resolved = await ps.resolve_model("gpt-4o")
    assert resolved is not None
    assert resolved["api_key"] == "sk-secret-123"
    assert resolved["provider_name"] == "openai"
    resolved_by_id = await ps.resolve_model_by_id(model["id"])
    assert resolved_by_id is not None
    assert resolved_by_id["model_id"] == model["id"]

    # 3. 저장 시 ciphertext 는 v3:, 평문 미포함
    async with factory() as s:
        row = (await s.execute(select(LlmProvider).where(LlmProvider.id == prov["id"]))).scalar_one()
        assert row.encrypted_api_key.startswith("v3:")
        assert "sk-secret-123" not in row.encrypted_api_key

    # 4. 미등록 모델 → resolve None (화이트리스트)
    assert await ps.resolve_model("no-such-model") is None

    # 5. 대화/메시지 + 소유권(user_id 기준, 프로젝트 무관)
    conv = await cs.create_conversation(project_id="p1", user_id="u1", title="t", model_name="gpt-4o")
    await cs.add_message(conv["id"], role="user", content="안녕하세요")
    msgs = await cs.list_messages(conv["id"], user_id="u1", project_id="p1")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "안녕하세요"
    with pytest.raises(cs.ConversationForbidden):
        await cs.get_conversation(conv["id"], user_id="other-user", project_id="p1")

    # 6. apply_usage — 원자적 used_quota UPDATE + 원장 append
    credited = await credit.apply_usage(
        event_id="usage-1",
        user_id="u1",
        project_id="p1",
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        usage_cost=_usage_cost(Decimal("0.002")),
        margin_multiplier=Decimal("1.5"),
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
        assert logs[0].event_id == "usage-1"
        assert logs[0].pricing_status == "priced"
        assert logs[0].pricing_snapshot["credited_cost"] == "3.00000000"

    # 7. 두 번째 과금 → 누적(원자적 증가)
    await credit.apply_usage(
        event_id="usage-2",
        user_id="u1",
        project_id="p1",
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=10,
        usage_cost=_usage_cost(Decimal("0.001")),
        margin_multiplier=Decimal("1"),
        conversation_id=conv["id"],
        source="web",
    )
    duplicate = await credit.apply_usage(
        event_id="usage-2",
        user_id="u1",
        project_id="p1",
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=10,
        usage_cost=_usage_cost(Decimal("99")),
        margin_multiplier=Decimal("9"),
        conversation_id=conv["id"],
        source="web",
    )
    assert duplicate == Decimal("1.00000000")
    async with factory() as s:
        wallet = await s.get(UserWallet, "u1")
        assert wallet.used_quota_this_month == Decimal("4.00000000")  # 3 + 1
        logs = (await s.execute(select(ChatUsageLog).where(ChatUsageLog.user_id == "u1"))).scalars().all()
        assert len(logs) == 2

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


async def test_conversation_project_scope_cross_project(chat_db):
    """The same user cannot access a conversation through another project scope."""
    from app.services.chat import conversation_store as cs

    c1 = await cs.create_conversation(project_id="projA", user_id="u1", title="A", model_name="m")
    c2 = await cs.create_conversation(project_id="projB", user_id="u1", title="B", model_name="m")
    await cs.create_conversation(project_id="projA", user_id="u2", title="타인", model_name="m")

    assert {c["id"] for c in await cs.list_conversations(user_id="u1", project_id="projA")} == {c1["id"]}
    assert {c["id"] for c in await cs.list_conversations(user_id="u1", project_id="projB")} == {c2["id"]}

    with pytest.raises(cs.ConversationForbidden):
        await cs.get_conversation(c2["id"], user_id="u1", project_id="projA")
    with pytest.raises(cs.ConversationForbidden):
        await cs.get_conversation(c1["id"], user_id="u2", project_id="projA")
    with pytest.raises(cs.ConversationForbidden):
        await cs.delete_conversation(c1["id"], user_id="u1", project_id="projB")


async def test_persistent_run_creation_is_atomic(chat_db, execution_snapshots):
    from app.models.chat_runs import ChatRun, ChatRunEventRow, ChatRunProvider
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs

    capability_snapshot, pricing_snapshot = execution_snapshots
    conv = await cs.create_conversation(project_id="projA", user_id="u1", title="A", model_name="m")
    descriptor = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="4af6725e-bf56-4a57-a5a3-0e750112340f",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "hello"}],
            "features": {},
        },
        conversation_id=conv["id"],
        model_name="m",
        agent_id=None,
        user_content="hello",
        user_parts=[{"type": "text", "text": "hello"}],
        request_payload={"input_messages": [{"role": "user", "content": "hello"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )
    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        messages = await cs.list_messages(conv["id"], user_id="u1", project_id="projA")
        events = (
            (
                await session.execute(
                    select(ChatRunEventRow)
                    .where(ChatRunEventRow.run_id == descriptor.run_id)
                    .order_by(ChatRunEventRow.seq)
                )
            )
            .scalars()
            .all()
        )
        provider_rows = (
            (await session.execute(select(ChatRunProvider).where(ChatRunProvider.run_id == descriptor.run_id)))
            .scalars()
            .all()
        )
    assert run is not None and run.user_message_id == messages[-1]["id"]
    assert messages[-1]["content"] == "hello"
    assert [event.event_type for event in events] == ["run.started", "run.stage.changed"]
    assert run.capability_snapshot == capability_snapshot
    assert run.pricing_snapshot == pricing_snapshot
    assert [(row.provider_id, row.model_id, row.config_version_hash) for row in provider_rows] == [
        (
            capability_snapshot["provider_id"],
            capability_snapshot["model_id"],
            capability_snapshot["config_version_hash"],
        )
    ]


async def test_worker_batches_slow_journal_delta_writes(chat_db, execution_snapshots, monkeypatch):
    from app.models.chat_runs import ChatRun, ChatRunEventRow, ChatRunSegment, ChatRunTurn
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import decrypt_chat_content

    capability_snapshot, pricing_snapshot = execution_snapshots

    conv = await cs.create_conversation(project_id="projA", user_id="u1", title="A", model_name="m")
    descriptor = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="59b6a901-0965-4ae4-818c-76ca4a01e6a7",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "hello"}],
            "features": {},
        },
        conversation_id=conv["id"],
        model_name="m",
        agent_id=None,
        user_content="hello",
        user_parts=[{"type": "text", "text": "hello"}],
        request_payload={"input_messages": [{"role": "user", "content": "hello"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )
    streamed_text = "x" * 398 + " \n"

    async def fake_resolve_model(_capability_snapshot):
        return {
            "provider_type": "openai",
            "api_base": None,
            "api_key": "test",
            "model_name": "m",
            "provider_name": "executor-provider",
        }

    async def fake_stream(**kwargs):
        hooks = kwargs["execution_hooks"]
        assert await hooks.provider_started(round_index=0, attempt=1) is None
        await hooks.provider_completed(
            round_index=0,
            attempt=1,
            usage={"prompt_tokens": 1, "completion_tokens": 400},
            result_payload={
                "text": streamed_text,
                "tool_calls": [],
                "citations": [],
                "usage": {"prompt_tokens": 1, "completion_tokens": 400},
            },
        )
        assert (
            await hooks.tool_started(
                round_index=0,
                tool_index=0,
                tool_call_id="call_1",
                tool_name="list_my_conversations",
            )
            is None
        )
        await hooks.tool_completed(
            round_index=0,
            tool_index=0,
            tool_call_id="call_1",
            tool_name="list_my_conversations",
            result_payload={"content": "[]"},
        )
        provider_replay = await hooks.provider_started(round_index=0, attempt=1)
        assert provider_replay is not None
        assert provider_replay["text"] == streamed_text
        tool_replay = await hooks.tool_started(
            round_index=0,
            tool_index=0,
            tool_call_id="call_1",
            tool_name="list_my_conversations",
        )
        assert tool_replay == {"content": "[]", "_durable_replay": True}
        for token in streamed_text:
            yield {"type": "token", "text": token}
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 400}}

    part_delta_writes = 0
    monkeypatch.setattr(durable_runs, "monotonic", lambda: 0.0)
    original_append = durable_runs._append

    async def slow_append(run_id, event_type, payload, *, owner):
        nonlocal part_delta_writes
        if event_type == "part.delta":
            part_delta_writes += 1
            await asyncio.sleep(0.001)
        await original_append(run_id, event_type, payload, owner=owner)

    monkeypatch.setattr(durable_runs.ps, "resolve_model_snapshot", fake_resolve_model)
    monkeypatch.setattr(durable_runs.engine, "stream", fake_stream)
    monkeypatch.setattr(durable_runs, "_append", slow_append)

    assert await durable_runs.execute_queued_run(descriptor.run_id, owner="worker-test") is True
    assert part_delta_writes == 4

    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        segment = await session.get(ChatRunSegment, (descriptor.run_id, "provider:0:1"))
        tool_segment = await session.get(ChatRunSegment, (descriptor.run_id, "tool:0:0"))
        turn = await session.get(ChatRunTurn, (descriptor.run_id, 0))
        rows = (
            await session.execute(
                select(ChatRunEventRow)
                .where(ChatRunEventRow.run_id == descriptor.run_id, ChatRunEventRow.event_type == "part.delta")
                .order_by(ChatRunEventRow.seq)
            )
        ).scalars()
        deltas = [json.loads(decrypt_chat_content(row.payload))["delta"] for row in rows]
        stage_rows = (
            await session.execute(
                select(ChatRunEventRow)
                .where(
                    ChatRunEventRow.run_id == descriptor.run_id,
                    ChatRunEventRow.event_type == "run.stage.changed",
                )
                .order_by(ChatRunEventRow.seq)
            )
        ).scalars()
        stages = [json.loads(decrypt_chat_content(row.payload))["stage"] for row in stage_rows]
    assert run.status == "completed"
    assert segment is not None and segment.status == "completed"
    assert tool_segment is not None and tool_segment.status == "completed"
    assert turn is not None and turn.assistant_message_id == run.assistant_message_id
    assert turn.message_event_seq is not None
    assert "".join(deltas) == streamed_text
    assert stages == ["queued", "model_request", "model_response", "response_writing", "finalizing"]

    async def failing_stream(**_kwargs):
        for _ in range(50):
            yield {"type": "token", "text": "y"}
        yield {"type": "error", "message": "upstream stopped"}

    failed = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="6932b5f2-9c46-46d8-9b0b-edb1d973b878",
        intent={"endpoint": "completion", "model_id": "m", "parts": [{"type": "text", "text": "fail"}], "features": {}},
        conversation_id=conv["id"],
        model_name="m",
        agent_id=None,
        user_content="fail",
        user_parts=[{"type": "text", "text": "fail"}],
        request_payload={"input_messages": [{"role": "user", "content": "fail"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )
    monkeypatch.setattr(durable_runs.engine, "stream", failing_stream)
    assert await durable_runs.execute_queued_run(failed.run_id, owner="worker-test") is True

    async with factory() as session:
        failed_run = await session.get(ChatRun, failed.run_id)
        failed_rows = (
            await session.execute(
                select(ChatRunEventRow)
                .where(ChatRunEventRow.run_id == failed.run_id, ChatRunEventRow.event_type == "part.delta")
                .order_by(ChatRunEventRow.seq)
            )
        ).scalars()
        failed_deltas = [json.loads(decrypt_chat_content(row.payload))["delta"] for row in failed_rows]
    assert failed_run.status == "failed"
    assert "".join(failed_deltas) == "y" * 50

    async def indeterminate_stream(**_kwargs):
        yield {
            "type": "error",
            "code": "provider_result_unknown",
            "message": "provider result is indeterminate",
        }

    indeterminate = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="0d3d93ba-4f06-44f1-bef0-f4cce391f97f",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "indeterminate"}],
            "features": {},
        },
        conversation_id=conv["id"],
        model_name="m",
        agent_id=None,
        user_content="indeterminate",
        user_parts=[{"type": "text", "text": "indeterminate"}],
        request_payload={"input_messages": [{"role": "user", "content": "indeterminate"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )
    monkeypatch.setattr(durable_runs.engine, "stream", indeterminate_stream)
    assert await durable_runs.execute_queued_run(indeterminate.run_id, owner="worker-test") is True

    async with factory() as session:
        error_row = (
            await session.execute(
                select(ChatRunEventRow)
                .where(
                    ChatRunEventRow.run_id == indeterminate.run_id,
                    ChatRunEventRow.event_type == "run.failed",
                )
                .order_by(ChatRunEventRow.seq.desc())
            )
        ).scalar_one()
    assert json.loads(decrypt_chat_content(error_row.payload))["error_code"] == "provider_result_unknown"

    async def reasoning_only_stream(**_kwargs):
        yield {"type": "reasoning", "text": "reasoning only"}
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 0}}

    reasoning_run = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="31d7a03d-0d3d-46fb-8a87-53bf7be443db",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "reason"}],
            "features": {},
        },
        conversation_id=conv["id"],
        model_name="m",
        agent_id=None,
        user_content="reason",
        user_parts=[{"type": "text", "text": "reason"}],
        request_payload={"input_messages": [{"role": "user", "content": "reason"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )
    monkeypatch.setattr(durable_runs.engine, "stream", reasoning_only_stream)
    assert await durable_runs.execute_queued_run(reasoning_run.run_id, owner="worker-test") is True

    async with factory() as session:
        reasoning_rows = (
            await session.execute(
                select(ChatRunEventRow)
                .where(
                    ChatRunEventRow.run_id == reasoning_run.run_id,
                    ChatRunEventRow.event_type.in_(("part.delta", "part.completed")),
                )
                .order_by(ChatRunEventRow.seq)
            )
        ).scalars()
        reasoning_events = [json.loads(decrypt_chat_content(row.payload)) for row in reasoning_rows]
    assert [event["part_index"] for event in reasoning_events] == [1, 1]

    async def usage_only_stream(**_kwargs):
        yield {"type": "usage", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    canceled = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="8ca1cbde-785f-4e5f-bc51-3bfc7f4c2ac4",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "cancel"}],
            "features": {},
        },
        conversation_id=conv["id"],
        model_name="m",
        agent_id=None,
        user_content="cancel",
        user_parts=[{"type": "text", "text": "cancel"}],
        request_payload={"input_messages": [{"role": "user", "content": "cancel"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )

    async def cancel_requested(_run_id):
        return True

    monkeypatch.setattr(durable_runs.engine, "stream", usage_only_stream)
    monkeypatch.setattr(durable_runs, "_cancel_requested", cancel_requested)
    assert await durable_runs.execute_queued_run(canceled.run_id, owner="worker-test") is True
    async with factory() as session:
        canceled_run = await session.get(ChatRun, canceled.run_id)
    assert canceled_run.status == "canceled"


async def test_worker_projects_failed_policy_limit_tool_result(chat_db, execution_snapshots, monkeypatch):
    from app.models.chat_db import ChatMessage, ChatUsageLog
    from app.models.chat_runs import ChatRun, ChatRunEventRow, ChatRunSegment, ChatRunTurn
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.chat.message_parts import deserialize_parts
    from app.services.k3s_crypto import decrypt_chat_content

    capability_snapshot, pricing_snapshot = execution_snapshots
    conversation = await cs.create_conversation(project_id="projA", user_id="u1", title="turns", model_name="m")
    descriptor = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="fcb64a38-47a2-4c5a-a0a1-ae1fefcd3699",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "turns"}],
            "features": {},
        },
        conversation_id=conversation["id"],
        model_name="m",
        agent_id=None,
        user_content="turns",
        user_parts=[{"type": "text", "text": "turns"}],
        request_payload={"input_messages": [{"role": "user", "content": "turns"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )

    async def fake_resolve_model(_snapshot):
        return {
            "provider_type": "openai",
            "api_base": None,
            "api_key": "test",
            "model_name": "m",
            "provider_name": "executor-provider",
        }

    async def fake_stream(**kwargs):
        hooks = kwargs["execution_hooks"]
        assert await hooks.provider_started(round_index=0, attempt=1) is None
        yield {"type": "token", "text": "draft"}
        await hooks.provider_completed(
            round_index=0,
            attempt=1,
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            result_payload={"text": "draft", "tool_calls": [], "citations": [], "usage": {}},
        )
        assert (
            await hooks.tool_started(
                round_index=0,
                tool_index=0,
                tool_call_id="call_1",
                tool_name="builtin_read_status",
                arguments={},
            )
            is None
        )
        yield {
            "type": "tool_call",
            "tool_call_id": "call_1",
            "name": "builtin_read_status",
            "args": "{}",
            "_durable_journaled": True,
        }
        await hooks.tool_completed(
            round_index=0,
            tool_index=0,
            tool_call_id="call_1",
            tool_name="builtin_read_status",
            result_payload={
                "content": "Tool call exceeded the run policy limit.",
                "status": "failed",
                "error_code": "policy_limit_exceeded",
            },
        )
        yield {
            "type": "tool_result",
            "tool_call_id": "call_1",
            "name": "builtin_read_status",
            "content": "Tool call exceeded the run policy limit.",
            "status": "failed",
            "error_code": "policy_limit_exceeded",
            "_durable_journaled": True,
        }
        assert await hooks.provider_started(round_index=1, attempt=1) is None
        yield {"type": "token", "text": "final"}
        await hooks.provider_completed(
            round_index=1,
            attempt=1,
            usage={"prompt_tokens": 2, "completion_tokens": 2},
            result_payload={"text": "final", "tool_calls": [], "citations": [], "usage": {}},
        )
        yield {"type": "usage", "usage": {"prompt_tokens": 3, "completion_tokens": 3}}

    monkeypatch.setattr(durable_runs.ps, "resolve_model_snapshot", fake_resolve_model)
    monkeypatch.setattr(durable_runs.engine, "stream", fake_stream)
    assert await durable_runs.execute_queued_run(descriptor.run_id, owner="worker-test") is True

    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        turns = (
            (
                await session.execute(
                    select(ChatRunTurn).where(ChatRunTurn.run_id == descriptor.run_id).order_by(ChatRunTurn.ordinal)
                )
            )
            .scalars()
            .all()
        )
        messages = [await session.get(ChatMessage, turn.assistant_message_id) for turn in turns]
        tool_segment = await session.get(ChatRunSegment, (descriptor.run_id, "tool:0:0"))
        tool_events = (
            (
                await session.execute(
                    select(ChatRunEventRow.event_type)
                    .where(
                        ChatRunEventRow.run_id == descriptor.run_id,
                        ChatRunEventRow.event_type.in_(("tool.call.started", "tool.call.completed")),
                    )
                    .order_by(ChatRunEventRow.seq)
                )
            )
            .scalars()
            .all()
        )
        usage_log = (
            await session.execute(select(ChatUsageLog).where(ChatUsageLog.event_id == f"run:{descriptor.run_id}"))
        ).scalar_one()
        persisted_parts = [
            [part.model_dump(by_alias=True, exclude_none=True) for part in deserialize_parts(message.parts)]
            for message in messages
        ]
        replayed = await durable_runs.replay_events(session, run, after_seq=0)
    public_messages = await cs.list_messages(conversation["id"], user_id="u1", project_id="projA")
    assert [turn.ordinal for turn in turns] == [0, 1]
    assert all(turn.message_event_seq is not None for turn in turns)
    assert all(turn.completion_event_seq is not None for turn in turns)
    assert [decrypt_chat_content(message.content) for message in messages] == ["draft", "final"]
    assert [message.status for message in messages] == ["complete", "complete"]
    assert [(message.token_prompt, message.token_completion) for message in messages] == [(0, 0), (3, 3)]
    assert run.assistant_message_id == turns[-1].assistant_message_id
    assert tool_segment is not None
    assert tool_segment.started_event_seq is not None
    assert tool_segment.completed_event_seq is not None
    assert tool_events == ["tool.call.started", "tool.call.completed"]
    completed_event = next(event for event in replayed if event.type == "tool.call.completed")
    assert completed_event.payload.status == "failed"
    assert completed_event.payload.error_code == "policy_limit_exceeded"
    assert [component["kind"] for component in usage_log.usage_components] == ["input_tokens", "output_tokens"]
    assert [part["type"] for part in persisted_parts[0]] == ["text", "tool_call", "tool_result"]
    assert persisted_parts[0][1]["name"] == "builtin_read_status"
    assert persisted_parts[0][2] == {
        "type": "tool_result",
        "call_id": "call_1",
        "name": "builtin_read_status",
        "content": [{"type": "text", "text": "Tool call exceeded the run policy limit."}],
        "is_error": True,
    }
    assert public_messages[1]["parts"] == persisted_parts[0]
    assert public_messages[1]["execution"] is None
    execution = public_messages[2]["execution"]
    assert execution is not None
    assert {key: execution[key] for key in ("run_id", "agent_id", "skill_ids", "skills")} == {
        "run_id": descriptor.run_id,
        "agent_id": None,
        "skill_ids": [],
        "skills": [],
    }
    assert len(execution["activity"]) == 1
    activity = execution["activity"][0]
    assert {
        key: activity[key]
        for key in (
            "id",
            "kind",
            "callId",
            "name",
            "source",
            "category",
            "arguments",
            "status",
            "content",
            "errorCode",
        )
    } == {
        "id": "tool:call_1",
        "kind": "tool",
        "callId": "call_1",
        "name": "builtin_read_status",
        "source": "builtin",
        "category": "기본 도구",
        "arguments": {},
        "status": "failed",
        "content": [{"type": "text", "text": "Tool call exceeded the run policy limit."}],
        "errorCode": "policy_limit_exceeded",
    }
    assert isinstance(activity["seq"], int)
    assert activity["createdAt"]
    assert isinstance(activity["durationMs"], int)
    assert (public_messages[2]["token_prompt"], public_messages[2]["token_completion"]) == (3, 3)


async def test_worker_persists_valid_structured_output_parts(chat_db, execution_snapshots, monkeypatch):
    from app.models.chat_db import ChatMessage
    from app.models.chat_runs import ChatRun
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.chat.message_parts import deserialize_parts

    capability_snapshot, pricing_snapshot = execution_snapshots
    conversation = await cs.create_conversation(project_id="projA", user_id="u1", title="structured", model_name="m")
    response_format = {
        "kind": "json_schema",
        "name": "answer",
        "version": "1",
        "schema": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
    }
    descriptor = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="99584a88-b96a-4fef-a114-f520eb6cbef5",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "structured"}],
            "features": response_format,
        },
        conversation_id=conversation["id"],
        model_name="m",
        agent_id=None,
        user_content="structured",
        user_parts=[{"type": "text", "text": "structured"}],
        request_payload={
            "input_messages": [{"role": "user", "content": "structured"}],
            "features": {"response_format": response_format},
        },
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )

    async def fake_resolve_model(_snapshot):
        return {
            "provider_type": "openai",
            "api_base": None,
            "api_key": "test",
            "model_name": "m",
            "provider_name": "executor",
        }

    async def fake_stream(**kwargs):
        assert kwargs["response_format"] == {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True, "schema": response_format["schema"]},
        }
        hooks = kwargs["execution_hooks"]
        assert await hooks.provider_started(round_index=0, attempt=1) is None
        yield {"type": "reasoning", "text": "visible analysis"}
        yield {"type": "citations", "items": [{"citation_id": "source-1", "url": "https://example.test/source"}]}
        yield {"type": "token", "text": '{"answer":"ok"}'}
        await hooks.provider_completed(
            round_index=0,
            attempt=1,
            usage={"prompt_tokens": 1, "completion_tokens": 2},
            result_payload={
                "text": '{"answer":"ok"}',
                "reasoning": "visible analysis",
                "tool_calls": [],
                "citations": [],
                "usage": {},
            },
        )
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 2}}

    monkeypatch.setattr(durable_runs.ps, "resolve_model_snapshot", fake_resolve_model)
    monkeypatch.setattr(durable_runs.engine, "stream", fake_stream)
    assert await durable_runs.execute_queued_run(descriptor.run_id, owner="worker") is True

    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        message = await session.get(ChatMessage, run.assistant_message_id)
    stored_parts = [part.model_dump(by_alias=True, exclude_none=True) for part in deserialize_parts(message.parts)]
    assert stored_parts == [
        {
            "type": "structured",
            "schema_name": "answer",
            "schema_version": "1",
            "value": {"answer": "ok"},
            "valid": True,
        },
        {"type": "reasoning", "text": "visible analysis", "visibility": "user"},
        {"type": "citation", "citation_id": "source-1", "url": "https://example.test/source", "source_kind": "web"},
    ]
    public_messages = await cs.list_messages(conversation["id"], user_id="u1", project_id="projA")
    assert public_messages[1]["parts"] == stored_parts
    assert public_messages[1]["citations"] == [stored_parts[-1]]


async def test_worker_replays_completed_provider_without_duplicate_projection(
    chat_db, execution_snapshots, monkeypatch
):
    from app.models.chat_db import ChatMessage
    from app.models.chat_runs import ChatRun, ChatRunEventRow, ChatRunTurn
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import decrypt_chat_content

    capability_snapshot, pricing_snapshot = execution_snapshots
    conversation = await cs.create_conversation(project_id="projA", user_id="u1", title="replay", model_name="m")
    descriptor = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="88b4a88b-31d8-4fef-a114-f520eb6cbef5",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "replay"}],
            "features": {},
        },
        conversation_id=conversation["id"],
        model_name="m",
        agent_id=None,
        user_content="replay",
        user_parts=[{"type": "text", "text": "replay"}],
        request_payload={"input_messages": [{"role": "user", "content": "replay"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )

    async def fake_resolve_model(_snapshot):
        return {
            "provider_type": "openai",
            "api_base": None,
            "api_key": "test",
            "model_name": "m",
            "provider_name": "executor-provider",
        }

    async def crash_after_provider_checkpoint(**kwargs):
        hooks = kwargs["execution_hooks"]
        assert await hooks.provider_started(round_index=0, attempt=1) is None
        await hooks.provider_completed(
            round_index=0,
            attempt=1,
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            result_payload={"text": "durable reply", "tool_calls": [], "citations": [], "usage": {}},
        )
        yield {"type": "token", "text": "durable reply"}
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        raise durable_runs.DurableRunLeaseLost("simulated worker crash")

    async def replay_checkpointed_provider(**kwargs):
        hooks = kwargs["execution_hooks"]
        replay = await hooks.provider_started(round_index=0, attempt=1)
        assert replay is not None and replay["_durable_replay"] is True
        yield {"type": "token", "text": replay["text"], "_durable_replay": True}
        yield {"type": "usage", "usage": replay["usage"]}

    monkeypatch.setattr(durable_runs.ps, "resolve_model_snapshot", fake_resolve_model)
    monkeypatch.setattr(durable_runs.engine, "stream", crash_after_provider_checkpoint)
    assert await durable_runs.execute_queued_run(descriptor.run_id, owner="worker-one") is True

    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        run = await session.get(ChatRun, descriptor.run_id, with_for_update=True)
        assert run is not None and run.status == "running"
        run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert await durable_runs.recover_stale_runs(owner="worker-two") == [descriptor.run_id]

    monkeypatch.setattr(durable_runs.engine, "stream", replay_checkpointed_provider)
    assert await durable_runs.execute_queued_run(descriptor.run_id, owner="worker-two") is True

    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        turn = await session.get(ChatRunTurn, (descriptor.run_id, 0))
        message = await session.get(ChatMessage, run.assistant_message_id)
        rows = (
            (
                await session.execute(
                    select(ChatRunEventRow)
                    .where(
                        ChatRunEventRow.run_id == descriptor.run_id,
                        ChatRunEventRow.event_type.in_(("part.delta", "part.completed")),
                    )
                    .order_by(ChatRunEventRow.seq)
                )
            )
            .scalars()
            .all()
        )
    payloads = [json.loads(decrypt_chat_content(row.payload)) for row in rows]
    assert run.status == "completed"
    assert turn is not None and turn.completion_event_seq is not None
    assert decrypt_chat_content(message.content) == "durable reply"
    assert [payload["delta"] for payload in payloads if "delta" in payload] == ["durable reply"]
    assert len([payload for payload in payloads if "part" in payload]) == 1


async def test_worker_shutdown_leaves_started_segment_for_recovery(chat_db, execution_snapshots, monkeypatch):
    from app.models.chat_db import ChatMessage
    from app.models.chat_runs import ChatRun, ChatRunSegment, ChatRunTurn
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import decrypt_chat_content

    capability_snapshot, pricing_snapshot = execution_snapshots
    conversation = await cs.create_conversation(project_id="projA", user_id="u1", title="shutdown", model_name="m")
    descriptor = await durable_runs.create_persistent_run(
        project_id="projA",
        user_id="u1",
        client_request_id="1f4c2cb6-9e23-4b89-baf7-d856379c7e3b",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "shutdown"}],
            "features": {},
        },
        conversation_id=conversation["id"],
        model_name="m",
        agent_id=None,
        user_content="shutdown",
        user_parts=[{"type": "text", "text": "shutdown"}],
        request_payload={"input_messages": [{"role": "user", "content": "shutdown"}], "features": {}},
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )

    async def fake_resolve_model(_snapshot):
        return {
            "provider_type": "openai",
            "api_base": None,
            "api_key": "test",
            "model_name": "m",
            "provider_name": "executor-provider",
        }

    async def canceled_stream(**kwargs):
        await kwargs["execution_hooks"].provider_started(round_index=0, attempt=1)
        yield {"type": "token", "text": "partial " * 32}
        raise asyncio.CancelledError()

    monkeypatch.setattr(durable_runs.ps, "resolve_model_snapshot", fake_resolve_model)
    monkeypatch.setattr(durable_runs.engine, "stream", canceled_stream)
    with pytest.raises(asyncio.CancelledError):
        await durable_runs.execute_queued_run(descriptor.run_id, owner="worker-test")

    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        run = await session.get(ChatRun, descriptor.run_id)
        segment = await session.get(ChatRunSegment, (descriptor.run_id, "provider:0:1"))
        run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert run.status == "running"
    assert segment.status == "provider_started"

    assert await durable_runs.recover_stale_runs(owner="recovery-worker") == []
    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        turn = await session.get(ChatRunTurn, (descriptor.run_id, 0))
        message = await session.get(ChatMessage, turn.assistant_message_id)
    assert run.status == "failed"
    assert message.status == "failed"
    assert decrypt_chat_content(message.content).strip() == ("partial " * 32).strip()


async def test_stale_run_recovery_requeues_pre_io_and_fails_started_boundaries(chat_db, execution_snapshots):
    from datetime import UTC, datetime, timedelta

    from app.models.chat_runs import ChatRun, ChatRunEventRow, ChatRunSegment
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.chat.run_store import (
        begin_segment_io,
        claim_queued_run,
        complete_segment_io,
        prepare_segment,
    )

    capability_snapshot, pricing_snapshot = execution_snapshots

    async def create_run(client_request_id: str, content: str):
        conversation = await cs.create_conversation(
            project_id="projA",
            user_id="u1",
            title=content,
            model_name="m",
        )
        return await durable_runs.create_persistent_run(
            project_id="projA",
            user_id="u1",
            client_request_id=client_request_id,
            intent={
                "endpoint": "completion",
                "model_id": "m",
                "parts": [{"type": "text", "text": content}],
                "features": {},
            },
            conversation_id=conversation["id"],
            model_name="m",
            agent_id=None,
            user_content=content,
            user_parts=[{"type": "text", "text": content}],
            request_payload={"input_messages": [{"role": "user", "content": content}], "features": {}},
            capability_snapshot=capability_snapshot,
            pricing_snapshot=pricing_snapshot,
        )

    started = await create_run("63ff0845-e7f8-4b3d-937f-90ab89c3843f", "started")
    completed = await create_run("a2c7cb55-e175-4eb9-8e8d-b13a5436fc2f", "completed")
    pre_io = await create_run("35de29f2-7ae6-484a-8f4c-60b32f7b95a2", "pre-io")
    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        started_run = await claim_queued_run(session, started.run_id, owner="lost-worker")
        completed_run = await claim_queued_run(session, completed.run_id, owner="lost-worker")
        pre_io_run = await claim_queued_run(session, pre_io.run_id, owner="lost-worker")
        assert started_run is not None and completed_run is not None and pre_io_run is not None
        segment = await prepare_segment(
            session,
            started_run,
            segment_id="provider:0:1",
            ordinal=1,
            endpoint="chat_completions",
            turn_ordinal=0,
        )
        begin_segment_io(segment)
        completed_segment = await prepare_segment(
            session,
            completed_run,
            segment_id="provider:0:1",
            ordinal=1,
            endpoint="chat_completions",
            turn_ordinal=0,
        )
        begin_segment_io(completed_segment)
        complete_segment_io(completed_segment, result_payload={"text": "complete"}, usage_payload=None)
        expired_at = datetime.now(UTC) - timedelta(seconds=1)
        started_run.lease_expires_at = expired_at
        pre_io_run.lease_expires_at = expired_at
        completed_run.lease_expires_at = expired_at

    assert set(await durable_runs.recover_stale_runs(owner="recovery-worker")) == {completed.run_id, pre_io.run_id}

    async with factory() as session:
        started_run = await session.get(ChatRun, started.run_id)
        pre_io_run = await session.get(ChatRun, pre_io.run_id)
        completed_run = await session.get(ChatRun, completed.run_id)
        segment = await session.get(ChatRunSegment, (started.run_id, "provider:0:1"))
        completed_segment = await session.get(ChatRunSegment, (completed.run_id, "provider:0:1"))
        failed_events = (
            (await session.execute(select(ChatRunEventRow.event_type).where(ChatRunEventRow.run_id == started.run_id)))
            .scalars()
            .all()
        )
    assert started_run.status == "failed"
    assert pre_io_run.status == "queued"
    assert completed_run.status == "queued"
    assert completed_segment.status == "completed"
    assert segment.status == "failed"
    assert "run.failed" in failed_events


async def test_first_temp_run_idempotency_reuses_thread(chat_db, execution_snapshots):
    from app.services.chat import durable_runs

    capability_snapshot, pricing_snapshot = execution_snapshots

    kwargs = {
        "project_id": "projA",
        "user_id": "u1",
        "client_request_id": "39e906a7-68a7-46ed-b56c-632d3a9a9c87",
        "intent": {
            "endpoint": "temp_completion",
            "temp_thread_id": None,
            "model_id": "m",
            "parts": [{"type": "text", "text": "hello"}],
            "features": {},
        },
        "temp_thread_id": None,
        "model_name": "m",
        "request_payload": {
            "input_messages": [{"role": "user", "content": "hello"}],
            "input_parts": [{"type": "text", "text": "hello"}],
            "features": {},
        },
        "capability_snapshot": capability_snapshot,
        "pricing_snapshot": pricing_snapshot,
    }
    first = await durable_runs.create_temp_run(**kwargs)
    second = await durable_runs.create_temp_run(**kwargs)

    assert second.run_id == first.run_id
    assert second.temp_thread_id == first.temp_thread_id


async def test_v2_temp_run_freezes_execution_policy_before_encryption(
    chat_db, execution_snapshots, chat_checkpointer_db, monkeypatch
):
    from app.models.chat_runs import ChatRun
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import decrypt_chat_content

    capability_snapshot, pricing_snapshot = execution_snapshots
    monkeypatch.setattr(durable_runs, "is_supported", lambda version: version in {1, 2})
    created = await durable_runs.create_temp_run(
        project_id="projA",
        user_id="u1",
        client_request_id="51a4b3f2-79ee-4e1d-82c5-7e6b29efee5d",
        intent={
            "endpoint": "temp_completion",
            "temp_thread_id": None,
            "model_id": "m",
            "parts": [{"type": "text", "text": "hello"}],
            "features": {},
        },
        temp_thread_id=None,
        model_name="m",
        request_payload={
            "input_messages": [{"role": "user", "content": "hello"}],
            "input_parts": [{"type": "text", "text": "hello"}],
            "features": {},
            "execution_policy": {
                "allowed_modes": ["chat"],
                "can_delegate_read": False,
                "can_delegate_write": False,
                "max_model_turns": 3,
                "max_tool_calls": 7,
                "max_children": 0,
                "max_parallel_children": 0,
                "max_child_depth": 0,
            },
        },
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
        execution_protocol_version=2,
    )

    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, created.run_id)

    payload = json.loads(decrypt_chat_content(run.request_payload))
    assert payload["execution_policy"]["max_model_turns"] == 3
    assert payload["v2_max_model_turns"] == 3
    assert payload["v2_max_tool_calls"] == 7


async def test_next_temp_run_includes_completed_thread_history(chat_db, execution_snapshots):
    from app.models.chat_runs import ChatRun
    from app.services.chat import durable_runs

    capability_snapshot, pricing_snapshot = execution_snapshots

    first_payload = {
        "input_messages": [{"role": "user", "content": "first question"}],
        "input_parts": [{"type": "text", "text": "first question"}],
        "features": {},
    }
    first = await durable_runs.create_temp_run(
        project_id="projA",
        user_id="u1",
        client_request_id="3dcedea4-e155-49d6-8b8d-0c08f21d8b8a",
        intent={
            "endpoint": "temp_completion",
            "temp_thread_id": None,
            "model_id": "m",
            "parts": first_payload["input_parts"],
            "features": {},
        },
        temp_thread_id=None,
        model_name="m",
        request_payload=first_payload,
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )
    factory = chat_db.get_session_factory()
    owner = "worker-test"
    async with factory() as session, session.begin():
        assert await durable_runs.claim_queued_run(session, first.run_id, owner=owner) is not None
    await durable_runs._append_temp_history(
        first.run_id,
        first_payload,
        [{"type": "text", "text": "first answer"}],
        owner=owner,
    )
    await durable_runs._finish(first.run_id, status="completed", message_id=None, owner=owner)

    second_payload = {
        "input_messages": [{"role": "user", "content": "second question"}],
        "input_parts": [{"type": "text", "text": "second question"}],
        "features": {},
    }
    second = await durable_runs.create_temp_run(
        project_id="projA",
        user_id="u1",
        client_request_id="6e0cc363-2c69-4652-bfa6-6e93d8ef09e3",
        intent={
            "endpoint": "temp_completion",
            "temp_thread_id": first.temp_thread_id,
            "model_id": "m",
            "parts": second_payload["input_parts"],
            "features": {},
        },
        temp_thread_id=first.temp_thread_id,
        model_name="m",
        request_payload=second_payload,
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
    )

    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, second.run_id)
    assert durable_runs._payload(run)["input_messages"] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
    ]


async def test_message_version_tree(chat_db):
    """버전 트리 실 로직: 재생성 형제·active_leaf 이동·backtrack 경로·분기 복사 독립성."""
    from app.services.chat import conversation_store as cs

    conv = await cs.create_conversation(project_id="p", user_id="u", title="t", model_name="m")
    cid = conv["id"]

    u1 = await cs.add_message(cid, role="user", content="Q1", parent_id=None, set_leaf=True)
    a1 = await cs.add_message(cid, role="assistant", content="A1", parent_id=u1["id"], model_name="m1", set_leaf=True)

    # 활성 경로 = [Q1, A1], leaf=a1
    path = await cs.get_active_path(cid, user_id="u", project_id="p")
    assert [m["content"] for m in path["messages"]] == ["Q1", "A1"]
    assert path["active_leaf_id"] == a1["id"]

    # 재생성: 대상 A1 의 턴-시작 user = Q1
    turn_user = await cs.find_turn_start_user(cid, user_id="u", project_id="p", message_id=a1["id"])
    assert turn_user["id"] == u1["id"]
    a2 = await cs.add_message(cid, role="assistant", content="A2", parent_id=u1["id"], model_name="m2", set_leaf=True)

    # 활성 경로가 형제 A2 로 이동
    path2 = await cs.get_active_path(cid, user_id="u", project_id="p")
    assert [m["content"] for m in path2["messages"]] == ["Q1", "A2"]
    assert path2["active_leaf_id"] == a2["id"]

    # 버전 전환: active_leaf 를 A1 로
    await cs.set_active_leaf(cid, user_id="u", project_id="p", message_id=a1["id"])
    path3 = await cs.get_active_path(cid, user_id="u", project_id="p")
    assert [m["content"] for m in path3["messages"]] == ["Q1", "A1"]

    # Initial page carries only the selected active branch, while lightweight
    # node metadata preserves the complete version tree for sibling controls.
    tree = await cs.list_message_tree(cid, user_id="u", project_id="p")
    assert [message["content"] for message in tree["messages"]] == ["Q1", "A1"]
    assert {node["id"] for node in tree["tree_nodes"]} == {u1["id"], a1["id"], a2["id"]}
    # 분기: A1 지점까지 새 대화로 복사(독립)
    forked = await cs.fork_conversation(cid, user_id="u", project_id="p", message_id=a1["id"])
    assert forked["parent_conversation_id"] == cid
    assert forked["forked_from_message_id"] == a1["id"]
    ftree = await cs.list_message_tree(forked["id"], user_id="u", project_id="p")
    assert [m["content"] for m in ftree["messages"]] == ["Q1", "A1"]
    assert len(ftree["tree_nodes"]) == 2
    assert forked["active_leaf_id"] == ftree["messages"][-1]["id"]
    # The original branch map remains intact, although its page stays active-only.
    original_tree = await cs.list_message_tree(cid, user_id="u", project_id="p")
    assert [message["content"] for message in original_tree["messages"]] == ["Q1", "A1"]
    assert {node["id"] for node in original_tree["tree_nodes"]} == {u1["id"], a1["id"], a2["id"]}

    # 콘텐츠 복호화 왕복(복사본도 평문 복원)
    assert ftree["messages"][0]["content"] == "Q1"


async def test_message_history_pages_active_branch_without_scanning_inactive_newer_versions(chat_db):
    """A newer inactive sibling must not evict the selected branch from the first page."""
    from app.services.chat import conversation_store as cs

    conv = await cs.create_conversation(project_id="p", user_id="u", title="paged", model_name="m")
    cid = conv["id"]
    parent_id = None
    root_id = None
    active_leaf = None
    for index in range(45):
        role = "user" if index % 2 == 0 else "assistant"
        message = await cs.add_message(
            cid,
            role=role,
            content=f"active-{index}",
            parent_id=parent_id,
            model_name="m" if role == "assistant" else None,
            set_leaf=True,
        )
        parent_id = message["id"]
        active_leaf = message["id"]
        if index == 0:
            root_id = message["id"]

    # Higher ID, but not the active branch. Old id-based paging would select it.
    await cs.add_message(
        cid, role="assistant", content="inactive-newer", parent_id=root_id, model_name="other", set_leaf=False
    )

    first = await cs.list_message_tree(cid, user_id="u", project_id="p", limit=40)
    assert first["active_leaf_id"] == active_leaf
    assert first["messages"][-1]["id"] == active_leaf
    assert first["has_more"] is True
    assert first["next_before_id"] == first["messages"][0]["parent_id"]
    assert any(node["id"] > active_leaf for node in first["tree_nodes"])

    older = await cs.list_message_tree(cid, user_id="u", project_id="p", before_id=first["next_before_id"], limit=40)
    assert [message["content"] for message in older["messages"]] == [f"active-{index}" for index in range(5)]


async def test_memory_outbox_claims_change_sequences_in_global_order(chat_db):
    """A later memory mutation cannot overtake an active earlier mutation."""
    from app.models.chat_db import ChatMemory
    from app.models.chat_jobs import ChatMemoryOutbox
    from app.services.chat.memory_outbox import claim_next

    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        memory = ChatMemory(user_id="outbox-user", scope="account", content="ciphertext")
        session.add(memory)
        await session.flush()
        session.add_all(
            [
                ChatMemoryOutbox(
                    event_key="outbox-order-first",
                    memory_id=memory.id,
                    mutation="upsert",
                    content_hash="a" * 64,
                    required_generations=[1],
                    applied_generations=[],
                    status="queued",
                ),
                ChatMemoryOutbox(
                    event_key="outbox-order-second",
                    memory_id=memory.id,
                    mutation="upsert",
                    content_hash="b" * 64,
                    required_generations=[1],
                    applied_generations=[],
                    status="queued",
                ),
            ]
        )

    async with factory() as session, session.begin():
        first = await claim_next(session, owner="first")
        assert first is not None
        first_sequence = first.change_seq

    async with factory() as session, session.begin():
        assert await claim_next(session, owner="second") is None

    async with factory() as session, session.begin():
        first = await session.get(ChatMemoryOutbox, first_sequence, with_for_update=True)
        first.status = "completed"
        first.lease_owner = None
        first.lease_expires_at = None

    async with factory() as session, session.begin():
        second = await claim_next(session, owner="second")
        assert second is not None
        assert second.change_seq > first_sequence


async def test_resource_policy_schema_persists_global_selection(chat_db):
    from app.models.db import ResourcePolicy

    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            ResourcePolicy(
                policy_key="builder.image",
                resource_kind="image",
                resource_id="image-id",
                resource_name="Ubuntu 24.04",
                constraints={"external_only": False},
                updated_by_user_id="admin",
            )
        )

    async with factory() as session:
        row = await session.get(ResourcePolicy, "builder.image")
        assert row is not None
        assert row.resource_id == "image-id"
        assert row.resource_name == "Ubuntu 24.04"


async def test_agent_crud_hub_clone(chat_db):
    """Agent storage enforces owner/project scope while retaining public-template cloning."""
    from sqlalchemy import select as _select

    from app.models.chat_db import ChatAgent
    from app.services.chat import agent_store as ags

    factory = chat_db.get_session_factory()
    source_project = "project-owner"
    clone_project = "project-clone"

    source = await ags.create_agent(
        owner_user_id="owner",
        project_id=source_project,
        name="리뷰 봇",
        description="코드 리뷰",
        instructions="너는 리뷰어야",
        model_name="gpt-4o",
        visibility="public",
    )
    async with factory() as session:
        row = (await session.execute(_select(ChatAgent).where(ChatAgent.id == source["id"]))).scalar_one()
        assert row.instructions.startswith("v3:")
        assert "리뷰어" not in row.instructions

    got = await ags.get_agent(source["id"], user_id="owner", project_id=source_project)
    assert got["instructions"] == "너는 리뷰어야" and got["is_owner"] is True
    assert [agent["id"] for agent in await ags.list_agents(user_id="owner", project_id=source_project)] == [
        source["id"]
    ]

    for operation in (
        ags.get_agent(source["id"], user_id="owner", project_id="project-other"),
        ags.update_agent(source["id"], user_id="owner", project_id="project-other", patch={"name": "탈취"}),
        ags.delete_agent(source["id"], user_id="owner", project_id="project-other"),
    ):
        with pytest.raises(ags.AgentNotFound):
            await operation

    private = await ags.create_agent(
        owner_user_id="owner",
        project_id=source_project,
        name="비밀",
        visibility="private",
    )
    with pytest.raises(ags.AgentNotFound):
        await ags.clone_agent(private["id"], user_id="owner", project_id="project-other")

    hub = await ags.list_public(query="리뷰", user_id="stranger", project_id=clone_project)
    assert any(agent["id"] == source["id"] for agent in hub)

    clone = await ags.clone_agent(source["id"], user_id="stranger", project_id=clone_project)
    assert clone["owner_user_id"] == "stranger"
    assert clone["visibility"] == "private"
    assert clone["cloned_from_id"] == source["id"]
    assert clone["instructions"] == "너는 리뷰어야"
    assert clone["mcp_ids"] == [] and clone["tool_ids"] == []
    assert (await ags.get_agent(source["id"], user_id="owner", project_id=source_project))["clone_count"] == 1

    await ags.update_agent(clone["id"], user_id="stranger", project_id=clone_project, patch={"name": "내 리뷰 봇"})
    assert (await ags.get_agent(clone["id"], user_id="stranger", project_id=clone_project))["name"] == "내 리뷰 봇"
    assert (await ags.get_agent(source["id"], user_id="owner", project_id=source_project))["name"] == "리뷰 봇"


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
    got = await cs.get_conversation(conv["id"], user_id="u1", project_id="p1")
    assert got["title"] == "비밀 제목"
    out = await cs.list_messages(conv["id"], user_id="u1", project_id="p1")
    assert out[0]["content"] == "비밀 응답"
    assert out[0]["tool_calls"] == [{"id": "c1", "name": "list_instances"}]


async def test_system_charge_does_not_debit_wallet(chat_db):
    """charge_wallet=False(제목 요약 등 시스템 부담)는 usage_logs 만 남기고 지갑 미차감."""
    from app.services.chat import credit

    factory = chat_db.get_session_factory()

    await credit.precheck("sysu", "p1")  # 지갑 생성(used=0)
    await credit.apply_usage(
        event_id="title:system-test",
        user_id="sysu",
        project_id="p1",
        model_name="gpt-4o-mini",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=4,
        usage_cost=_usage_cost(Decimal("0.0001")),
        margin_multiplier=Decimal("1"),
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
            event_id=f"{source}:{user}:{model}:{pt}:{ct}",
            user_id=user,
            project_id="p1",
            model_name=model,
            provider="openai",
            prompt_tokens=pt,
            completion_tokens=ct,
            usage_cost=_usage_cost(Decimal(str(raw))),
            margin_multiplier=Decimal("1"),
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


async def test_workspace_and_memory_roundtrip(chat_db):
    """워크스페이스/메모리 실 로직: 암호화 왕복·소유권·완료 주입용 조회."""
    from app.services.chat import conversation_store as cs
    from app.services.chat import memory_store as ms
    from app.services.chat import workspace_store as ws

    # 워크스페이스 생성 + instructions 암호화 왕복
    wsp = await ws.create_workspace(owner_user_id="wu", name="백엔드", instructions="FastAPI 규칙")
    assert (await ws.get_workspace(wsp["id"], user_id="wu"))["instructions"] == "FastAPI 규칙"
    with pytest.raises(ws.WorkspaceForbidden):
        await ws.get_workspace(wsp["id"], user_id="other")
    # 완료 경로 조회: 소유자면 지침, 타인이면 None(조용히 무시)
    assert await ws.get_instructions_for_run(wsp["id"], user_id="wu") == "FastAPI 규칙"
    assert await ws.get_instructions_for_run(wsp["id"], user_id="other") is None

    # 대화를 워크스페이스에 배정
    conv = await cs.create_conversation(project_id="p", user_id="wu", title="t", model_name="m", workspace_id=wsp["id"])
    assert conv["workspace_id"] == wsp["id"]
    moved = await cs.set_workspace(conv["id"], user_id="wu", project_id="p", workspace_id=None)
    assert moved["workspace_id"] is None
    other_wsp = await ws.create_workspace(owner_user_id="other", name="타인 프로젝트")
    with pytest.raises(cs.WorkspaceForbidden):
        await cs.create_conversation(
            project_id="p", user_id="wu", title="차단", model_name="m", workspace_id=other_wsp["id"]
        )
    with pytest.raises(cs.WorkspaceForbidden):
        await cs.set_workspace(conv["id"], user_id="wu", project_id="p", workspace_id=other_wsp["id"])

    # 메모리 암호화 왕복 + 활성 주입 조회(비활성 제외)
    m1 = await ms.create_memory(user_id="wu", content="사용자는 Python 선호")
    m2 = await ms.create_memory(user_id="wu", content="다크모드")
    await ms.update_memory(m2["id"], user_id="wu", patch={"is_active": False})
    active = await ms.active_contents_for_run(user_id="wu", project_id="project-a")
    assert "사용자는 Python 선호" in active
    assert "다크모드" not in active  # 비활성 제외
    with pytest.raises(ms.MemoryForbidden):
        await ms.update_memory(m1["id"], user_id="other", patch={"content": "탈취"})


async def test_models_dev_import_is_atomic_and_remap_safe(chat_db):
    """Exact catalog keys only; a conflicting remap cannot alter stored prices."""
    import json

    from app.models.chat_db import LlmModel
    from app.services.chat import models_dev
    from app.services.chat import provider_store as ps

    def catalog(provider_id: str, model_ids: list[str]):
        return models_dev.parse_catalog(
            json.dumps(
                {
                    "providers": {
                        provider_id: {
                            "id": provider_id,
                            "models": {
                                model_id: {"id": model_id, "cost": {"input": 2, "output": 8}} for model_id in model_ids
                            },
                        }
                    }
                }
            ),
            "2026-07-20T00:00:00+00:00",
        )

    provider = await ps.create_provider(name="catalog-provider")
    first = await ps.create_model(provider_id=provider["id"], model_name="first")
    second = await ps.create_model(provider_id=provider["id"], model_name="second")
    manual = await ps.create_model(
        provider_id=provider["id"],
        model_name="manual",
        input_price_per_million=Decimal("3"),
        output_price_per_million=Decimal("9"),
    )

    imported = await ps.import_models_dev_prices(
        local_provider_id=provider["id"],
        models_dev_provider_id="openai",
        selections=[
            {"local_model_id": first["id"], "models_dev_model_id": "openai/first"},
            {"local_model_id": second["id"], "models_dev_model_id": "openai/second"},
        ],
        catalog=catalog("openai", ["openai/first", "openai/second"]),
    )
    assert {row["id"] for row in imported} == {first["id"], second["id"]}

    factory = chat_db.get_session_factory()
    async with factory() as session:
        rows = {
            row.id: row
            for row in (await session.execute(select(LlmModel).where(LlmModel.provider_id == provider["id"]))).scalars()
        }
        assert rows[first["id"]].input_price == Decimal("0.0000020000")
        assert rows[first["id"]].output_price == Decimal("0.0000080000")
        assert rows[first["id"]].price_source == "models.dev"
        assert rows[first["id"]].price_metadata["cost"]["input"] == "2"
        rows[manual["id"]].models_dev_model_id = "stale/manual"
        await session.commit()

    with pytest.raises(ps.ModelsDevImportConflictError):
        await ps.import_models_dev_prices(
            local_provider_id=provider["id"],
            models_dev_provider_id="anthropic",
            selections=[{"local_model_id": first["id"], "models_dev_model_id": "anthropic/first"}],
            catalog=catalog("anthropic", ["anthropic/first"]),
        )

    async with factory() as session:
        provider_row = await session.get(LlmProvider, provider["id"])
        first_row = await session.get(LlmModel, first["id"])
        assert provider_row.models_dev_provider_id == "openai"
        assert first_row.models_dev_model_id == "openai/first"
        assert first_row.input_price == Decimal("0.0000020000")

    await ps.import_models_dev_prices(
        local_provider_id=provider["id"],
        models_dev_provider_id="anthropic",
        selections=[
            {"local_model_id": first["id"], "models_dev_model_id": "anthropic/first"},
            {"local_model_id": second["id"], "models_dev_model_id": "anthropic/second"},
        ],
        catalog=catalog("anthropic", ["anthropic/first", "anthropic/second"]),
    )
    async with factory() as session:
        manual_row = await session.get(LlmModel, manual["id"])
        assert manual_row.models_dev_model_id is None


async def test_api_key_create_verify_revoke_roundtrip(chat_db):
    """API 키: 발급(평문 1회) → 해시 저장(평문 미포함) → verify 왕복 → 폐기 후 verify None."""
    from app.services.chat import api_key_store as aks

    factory = chat_db.get_session_factory()

    issued = await aks.create_key("u-api", "p-api", "my key")
    raw = issued["key"]
    assert raw.startswith("sk-afgl-")
    key_id = issued["id"]

    # 저장은 해시만 — 평문 미포함
    from app.models.chat_db import ChatApiKey

    async with factory() as s:
        row = await s.get(ChatApiKey, key_id)
        assert row.key_hash != raw and raw not in row.key_hash
        assert len(row.key_hash) == 64

    # verify 왕복
    info = await aks.verify_key(raw)
    assert info == {"user_id": "u-api", "project_id": "p-api", "api_key_id": key_id}

    # 잘못된 키 → None
    assert await aks.verify_key("sk-afgl-wrong") is None

    # 타 소유자 폐기 → 403
    with pytest.raises(aks.ApiKeyForbidden):
        await aks.revoke_key(key_id, "other-user", "p-api")

    # 소유자 폐기 → 이후 verify None
    await aks.revoke_key(key_id, "u-api", "p-api")
    assert await aks.verify_key(raw) is None


async def test_usage_source_and_key_aggregation(chat_db):
    """web/api source + api_key_id 원장 → user 요약 by_source, stats.timeseries, by_api_key 집계."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.models.chat_db import ChatApiKey
    from app.services.chat import stats as stats_service
    from app.services.chat import usage as usage_service

    factory = chat_db.get_session_factory()
    async with factory() as s, s.begin():
        s.add(
            ChatApiKey(
                id=100,
                owner_user_id="u-agg",
                owner_project_id="p-agg",
                name="cli",
                key_prefix="sk-afgl-AAAA",
                key_hash="a" * 64,
                is_active=True,
            )
        )
        now = datetime.now(UTC)
        for src, kid, tok in (("web", None, 100), ("api", 100, 40), ("api", 100, 20), ("system", None, 5)):
            s.add(
                ChatUsageLog(
                    event_id=f"e-{src}-{kid}-{tok}",
                    project_id="p-agg",
                    user_id="u-agg",
                    model_name="gpt-4o",
                    prompt_tokens=tok,
                    completion_tokens=0,
                    raw_cost=Decimal("0.01"),
                    credited_cost=Decimal("0.02"),
                    source=src,
                    api_key_id=kid,
                    created_at=now,
                )
            )

    # 사용자 요약 by_source — system 제외, web/api 분리
    summary = await usage_service.user_usage_summary("u-agg", "p-agg")
    by_source = {r["source"]: r for r in summary["by_source"]}
    assert by_source["web"]["tokens"] == 100
    assert by_source["api"]["tokens"] == 60
    assert "system" not in by_source

    # timeseries(day) — source별 버킷 집계(본인, 시스템 제외)
    ts = await stats_service.timeseries("day", "all", None, user_id="u-agg", include_system=False)
    api_rows = [r for r in ts if r["source"] == "api"]
    assert sum(r["total_tokens"] for r in api_rows) == 60

    # by_api_key — 키 이름 조인 + api 만
    keys = await stats_service.by_api_key("all", None, user_id="u-agg")
    assert keys and keys[0]["api_key_id"] == 100 and keys[0]["name"] == "cli"
    assert keys[0]["total_tokens"] == 60


async def test_timeseries_fine_buckets_round_and_filter_in_mysql(chat_db):
    """5분/15분 집계는 MySQL에서 분 하한과 모델 필터를 정확히 적용한다."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.services.chat import stats as stats_service

    factory = chat_db.get_session_factory()
    hour_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    rows = (
        ("fine-1", "alpha", hour_start.replace(minute=2), 10, 1),
        ("fine-2", "beta", hour_start.replace(minute=6), 20, 2),
        ("fine-3", "alpha", hour_start.replace(minute=17), 30, 3),
        ("fine-other-project", "alpha", hour_start.replace(minute=4), 99, 9),
        ("fine-stale", "alpha", hour_start - timedelta(days=8), 999, 1),
    )
    async with factory() as session, session.begin():
        for event_id, model_name, created_at, prompt_tokens, completion_tokens in rows:
            session.add(
                ChatUsageLog(
                    event_id=event_id,
                    project_id="p-fine" if event_id != "fine-other-project" else "p-other",
                    user_id="u-fine",
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    raw_cost=Decimal("0"),
                    credited_cost=Decimal("0"),
                    source="web",
                    created_at=created_at,
                )
            )

    async def totals(bucket: str, *, model_name: str | None = None) -> dict[str, int]:
        result = await stats_service.timeseries(bucket, "all", "p-fine", model_name=model_name)
        aggregated: dict[str, int] = {}
        for row in result:
            aggregated[row["bucket"]] = aggregated.get(row["bucket"], 0) + row["total_tokens"]
        return aggregated

    def bucket(minutes: int) -> str:
        return f"{hour_start:%Y-%m-%d %H:}{minutes:02}:00"

    assert await totals("5m") == {
        bucket(0): 11,
        bucket(5): 22,
        bucket(15): 33,
    }
    assert await totals("15m") == {
        bucket(0): 33,
        bucket(15): 33,
    }
    assert await totals("5m", model_name="alpha") == {
        bucket(0): 11,
        bucket(15): 33,
    }


async def test_v2_durable_input_resolution_is_atomic_and_idempotent(chat_db, monkeypatch):
    from app.models.chat_agent_platform import ChatRunInteraction
    from app.models.chat_runs import ChatRun, ChatRunEventRow, ChatToolApproval
    from app.services.chat import durable_runs

    monkeypatch.setattr(durable_runs, "v2_runtime_ready", lambda _version: True)
    woke: list[str] = []

    async def wake(run_id: str) -> None:
        woke.append(run_id)

    monkeypatch.setattr(durable_runs, "wake_run", wake)
    run_id = "f86c642c-4f25-4274-a26d-11974f72f5b9"
    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            ChatRun(
                id=run_id,
                run_scope="conversation",
                project_id="approval-project",
                user_id="approval-user",
                model_name="approval-model",
                capability_snapshot={},
                pricing_snapshot={},
                client_request_id="e571a99e-298f-4caa-99b5-c94e2a2d1520",
                request_fingerprint="approval-test",
                fingerprint_version=1,
                execution_protocol_version=2,
                status="awaiting_input",
            )
        )
        await session.flush()
        expires_at = datetime.now(UTC) + timedelta(minutes=15)

        def approval(call_id: str, tool_name: str, expiry: datetime) -> ChatToolApproval:
            arguments = {"call_id": call_id}
            preview_fingerprint = durable_runs._approval_preview_fingerprint([])
            dispatch_hmac = durable_runs._approval_dispatch_hmac(
                run_id=run_id,
                owner_user_id="approval-user",
                project_id="approval-project",
                call_id=call_id,
                name=tool_name,
                arguments=arguments,
                source="workspace",
                effect="workspace_write",
                tool_definition_hash="a" * 64,
                config_fingerprint=None,
                destination_origin=None,
                preview_fingerprint=preview_fingerprint,
                expires_at=expiry,
            )
            return ChatToolApproval(
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments="{}",
                arguments_ciphertext=durable_runs.encrypt_chat_content(
                    json.dumps(arguments, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                ),
                dispatch_hmac=dispatch_hmac,
                preview_fingerprint=preview_fingerprint,
                source="workspace",
                effect="workspace_write",
                tool_definition_hash="a" * 64,
                status="pending",
                expires_at=expiry,
            )

        session.add_all(
            [
                approval("call-a", "workspace.write_file", expires_at),
                approval("call-b", "workspace.run", expires_at),
                approval("call-expired", "workspace.run", datetime.now(UTC) - timedelta(minutes=1)),
                ChatRunInteraction(
                    run_id=run_id,
                    id="75dcc8d9-dc8d-460b-a6ca-6a5fdd1e10d6",
                    status="pending",
                    request_ciphertext="v3:opaque-request",
                    response_schema={"option_ids": ["yes", "no"], "allow_multiple": False, "allow_text": True},
                    expires_at=expires_at,
                ),
            ]
        )

    first = await durable_runs.resolve_tool_approval(
        run_id=run_id,
        call_id="call-a",
        decision="approve",
        project_id="approval-project",
        user_id="approval-user",
    )
    assert first["status"] == "approved"
    assert first["run_status"] == "awaiting_input"
    assert first["pending_approvals"] == 2
    assert woke == []

    expired = await durable_runs.resolve_tool_approval(
        run_id=run_id,
        call_id="call-expired",
        decision="approve",
        project_id="approval-project",
        user_id="approval-user",
    )
    assert expired["decision"] == "deny"
    assert expired["status"] == "denied"
    assert expired["pending_approvals"] == 1

    final = await durable_runs.resolve_tool_approval(
        run_id=run_id,
        call_id="call-b",
        decision="deny",
        project_id="approval-project",
        user_id="approval-user",
    )
    assert final["status"] == "denied"
    assert final["run_status"] == "awaiting_input"
    assert final["pending_approvals"] == 0
    assert final["pending_interactions"] == 1
    assert woke == []

    interaction = await durable_runs.resolve_run_interaction(
        run_id=run_id,
        interaction_id="75dcc8d9-dc8d-460b-a6ca-6a5fdd1e10d6",
        response={"option_ids": ["yes"], "text": None},
        project_id="approval-project",
        user_id="approval-user",
    )
    assert interaction["status"] == "answered"
    assert interaction["run_status"] == "queued"
    assert interaction["pending_interactions"] == 0
    assert woke == [run_id]

    async with factory() as session, session.begin():
        run = await session.get(ChatRun, run_id, with_for_update=True)
        assert run is not None
        run.status = "running"

    repeated_interaction = await durable_runs.resolve_run_interaction(
        run_id=run_id,
        interaction_id="75dcc8d9-dc8d-460b-a6ca-6a5fdd1e10d6",
        response={"option_ids": ["yes"], "text": None},
        project_id="approval-project",
        user_id="approval-user",
    )
    assert repeated_interaction["status"] == "answered"
    assert repeated_interaction["run_status"] == "running"
    assert woke == [run_id]

    with pytest.raises(durable_runs.DurableRunConflict):
        await durable_runs.resolve_run_interaction(
            run_id=run_id,
            interaction_id="75dcc8d9-dc8d-460b-a6ca-6a5fdd1e10d6",
            response={"option_ids": ["no"], "text": None},
            project_id="approval-project",
            user_id="approval-user",
        )

    repeated = await durable_runs.resolve_tool_approval(
        run_id=run_id,
        call_id="call-b",
        decision="deny",
        project_id="approval-project",
        user_id="approval-user",
    )
    assert repeated["status"] == "denied"
    assert repeated["run_status"] == "running"
    assert repeated["pending_interactions"] == 0
    assert woke == [run_id]

    with pytest.raises(durable_runs.DurableRunConflict):
        await durable_runs.resolve_tool_approval(
            run_id=run_id,
            call_id="call-b",
            decision="approve",
            project_id="approval-project",
            user_id="approval-user",
        )

    async with factory() as session:
        run = await session.get(ChatRun, run_id)
        rows = (
            (
                await session.execute(
                    select(ChatRunEventRow.event_type)
                    .where(ChatRunEventRow.run_id == run_id)
                    .order_by(ChatRunEventRow.seq)
                )
            )
            .scalars()
            .all()
        )
    assert run is not None and run.status == "running"
    assert rows == [
        "tool.approval_resolved",
        "tool.approval_resolved",
        "tool.approval_resolved",
        "interaction.resolved",
        "run.stage.changed",
    ]


async def test_v2_input_expiry_sweep_skips_v1_rows_and_resumes_without_client(chat_db, monkeypatch):
    from app.models.chat_agent_platform import ChatRunInteraction
    from app.models.chat_runs import ChatRun, ChatToolApproval
    from app.services.chat import durable_runs

    monkeypatch.setattr(durable_runs, "v2_runtime_ready", lambda _version: True)
    woke: list[str] = []

    async def wake(run_id: str) -> None:
        woke.append(run_id)

    monkeypatch.setattr(durable_runs, "wake_run", wake)
    old_run_id = "473bf8cc-17c2-4d8d-b9ef-94ca621c2687"
    v2_run_id = "8df63a6f-d70e-4fbb-b838-3ce2c54d452e"
    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        session.add_all(
            [
                ChatRun(
                    id=old_run_id,
                    run_scope="conversation",
                    project_id="expiry-project",
                    user_id="expiry-user",
                    model_name="expiry-model",
                    capability_snapshot={},
                    pricing_snapshot={},
                    client_request_id="5d2bb22f-94ca-42e1-99c6-04ab83c7830c",
                    request_fingerprint="expiry-v1",
                    fingerprint_version=1,
                    execution_protocol_version=1,
                    status="awaiting_approval",
                ),
                ChatRun(
                    id=v2_run_id,
                    run_scope="conversation",
                    project_id="expiry-project",
                    user_id="expiry-user",
                    model_name="expiry-model",
                    capability_snapshot={},
                    pricing_snapshot={},
                    client_request_id="df3a5ffd-e153-4c34-88e0-4c190f98d11e",
                    request_fingerprint="expiry-v2",
                    fingerprint_version=1,
                    execution_protocol_version=2,
                    status="awaiting_input",
                ),
            ]
        )
        await session.flush()
        expired_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add_all(
            [
                ChatToolApproval(
                    run_id=old_run_id,
                    call_id="v1-call",
                    tool_name="legacy.write",
                    arguments="{}",
                    status="pending",
                    expires_at=expired_at,
                ),
                ChatToolApproval(
                    run_id=v2_run_id,
                    call_id="v2-call",
                    tool_name="workspace.write_file",
                    arguments="{}",
                    status="pending",
                    expires_at=expired_at,
                ),
                ChatRunInteraction(
                    run_id=v2_run_id,
                    id="45bf67b0-535c-4c86-a0d7-0bfbb4fe0f87",
                    status="pending",
                    request_ciphertext="v3:opaque-request",
                    response_schema={"option_ids": ["continue"], "allow_multiple": False, "allow_text": False},
                    expires_at=expired_at,
                ),
            ]
        )

    assert await durable_runs.expire_pending_inputs(limit=1) == [v2_run_id]
    assert woke == [v2_run_id]

    async with factory() as session:
        v1_approval = await session.get(ChatToolApproval, (old_run_id, "v1-call"))
        v2_approval = await session.get(ChatToolApproval, (v2_run_id, "v2-call"))
        v2_interaction = await session.get(ChatRunInteraction, (v2_run_id, "45bf67b0-535c-4c86-a0d7-0bfbb4fe0f87"))
        v2_run = await session.get(ChatRun, v2_run_id)
        assert v2_run is not None
        events = await durable_runs.replay_events(session, v2_run, after_seq=0)
        event_types = [event.type for event in events]
    assert v1_approval is not None and v1_approval.status == "pending"
    assert v2_approval is not None and v2_approval.status == "denied"
    assert v2_interaction is not None and v2_interaction.status == "timeout"
    assert v2_run is not None and v2_run.status == "queued"
    assert event_types == ["tool.approval_resolved", "interaction.resolved", "run.stage.changed"]
    assert events[0].payload.decided_by_user_id is None
    assert events[0].payload.decided_at is not None


async def test_v2_queued_cancellation_finalizes_pending_inputs_and_streaming_message(chat_db):
    from app.models.chat_agent_platform import ChatRunInteraction
    from app.models.chat_db import ChatConversation, ChatMessage
    from app.models.chat_runs import ChatRun, ChatToolApproval
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import decrypt_chat_content

    run_id = "a8ec3ee0-8a28-4e91-9d17-285d8f843b85"
    conversation_id = "9ced4b80-c986-4564-a941-85ddf79ddf5f"
    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            ChatConversation(
                id=conversation_id,
                project_id="cancel-project",
                user_id="cancel-user",
                title=None,
                model_name="cancel-model",
            )
        )
        await session.flush()
        message = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=None,
            status="streaming",
            model_name="cancel-model",
        )
        session.add(message)
        await session.flush()
        message_id = message.id
        run = ChatRun(
            id=run_id,
            run_scope="conversation",
            conversation_id=conversation_id,
            assistant_message_id=message.id,
            project_id="cancel-project",
            user_id="cancel-user",
            model_name="cancel-model",
            capability_snapshot={},
            pricing_snapshot={},
            client_request_id="ee2e1c7d-f529-497b-bb1c-3eb0ec377813",
            request_fingerprint="cancel-test",
            fingerprint_version=1,
            execution_protocol_version=2,
            status="queued",
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                ChatToolApproval(
                    run_id=run_id,
                    call_id="cancel-call",
                    tool_name="workspace.write_file",
                    arguments="{}",
                    status="pending",
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                ),
                ChatRunInteraction(
                    run_id=run_id,
                    id="c24e7647-0106-4de7-a673-8f143802f502",
                    status="pending",
                    request_ciphertext="v3:opaque-request",
                    response_schema={"option_ids": ["continue"], "allow_multiple": False, "allow_text": False},
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                ),
            ]
        )
        await durable_runs.append_event(
            session,
            run,
            durable_runs._event(
                run,
                "part.delta",
                {
                    "message_id": str(message_id),
                    "part_index": 0,
                    "part_type": "text",
                    "delta": "partial answer",
                },
            ),
        )

    cancelled = await durable_runs.request_cancelled(
        run_id=run_id,
        project_id="cancel-project",
        user_id="cancel-user",
    )
    assert cancelled.status == "canceled"
    assert cancelled.terminal

    async with factory() as session:
        run = await session.get(ChatRun, run_id)
        approval = await session.get(ChatToolApproval, (run_id, "cancel-call"))
        interaction = await session.get(ChatRunInteraction, (run_id, "c24e7647-0106-4de7-a673-8f143802f502"))
        message = await session.get(ChatMessage, message_id)
        assert run is not None
        events = await durable_runs.replay_events(session, run, after_seq=0)
    assert approval is not None and approval.status == "canceled"
    assert interaction is not None and interaction.status == "canceled"
    assert message is not None and message.status == "canceled"
    assert decrypt_chat_content(message.content or "") == "partial answer"
    assert [event.type for event in events] == [
        "part.delta",
        "tool.approval_resolved",
        "interaction.resolved",
        "run.stage.changed",
        "run.canceled",
    ]
    assert events[-1].payload.message_id == str(message_id)


async def test_v2_queued_cancellation_releases_matching_temp_thread(chat_db):
    from app.models.chat_runs import ChatRun, ChatTempThread
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import encrypt_chat_content

    run_id = "7c9479a8-a3f2-4e31-87e5-889c234d3dfa"
    thread_id = "c81df781-a4f2-4f5a-b9c1-2aef4bfd8e25"
    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            ChatTempThread(
                id=thread_id,
                project_id="cancel-project",
                user_id="cancel-user",
                history=encrypt_chat_content("[]"),
                active_run_id=run_id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        session.add(
            ChatRun(
                id=run_id,
                run_scope="temp",
                temp_thread_id=thread_id,
                project_id="cancel-project",
                user_id="cancel-user",
                model_name="cancel-model",
                capability_snapshot={},
                pricing_snapshot={},
                client_request_id="29e10a30-854a-46d4-a0c4-33f49293c52d",
                request_fingerprint="temp-cancel-test",
                fingerprint_version=1,
                execution_protocol_version=2,
                status="queued",
            )
        )

    cancelled = await durable_runs.request_cancelled(
        run_id=run_id,
        project_id="cancel-project",
        user_id="cancel-user",
    )
    assert cancelled.status == "canceled"

    async with factory() as session:
        thread = await session.get(ChatTempThread, thread_id)
    assert thread is not None
    assert thread.active_run_id is None


async def test_v2_graph_interrupt_persists_hmac_bound_approval_before_resume(
    chat_db, execution_snapshots, chat_checkpointer_db, monkeypatch
):
    from app.models.chat_runs import ChatRun, ChatToolApproval
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs
    from app.services.k3s_crypto import decrypt_chat_content

    monkeypatch.setattr(durable_runs, "is_supported", lambda version: version in {1, 2})
    monkeypatch.setattr(durable_runs, "SUPPORTED_EXECUTION_PROTOCOL_VERSIONS", {1, 2})
    capability_snapshot, pricing_snapshot = execution_snapshots
    conversation = await cs.create_conversation(
        project_id="pause-project",
        user_id="pause-user",
        title="Pause",
        model_name="m",
    )
    descriptor = await durable_runs.create_persistent_run(
        project_id="pause-project",
        user_id="pause-user",
        client_request_id="9d244277-2a9f-43f9-b2af-5247ec5b46f6",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "mutate"}],
            "features": {},
        },
        conversation_id=conversation["id"],
        model_name="m",
        agent_id=None,
        user_content="mutate",
        user_parts=[{"type": "text", "text": "mutate"}],
        request_payload={
            "input_messages": [{"role": "user", "content": "mutate"}],
            "features": {"tool_policy": {"approval_mode": "required_for_mutations"}},
        },
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
        execution_protocol_version=2,
    )

    async def interrupted_stream(**_kwargs):
        yield {
            "type": "input.interrupted",
            "payload": {
                "kind": "tool_approval",
                "calls": [
                    {
                        "call_id": "call-1",
                        "name": "custom__7__mutate_1",
                        "arguments": '{"value":"change"}',
                        "source": "custom_http",
                        "effect": "external_mutation",
                        "tool_definition_hash": "a" * 64,
                        "config_fingerprint": "b" * 64,
                        "destination_origin": "https://api.example.com",
                    }
                ],
            },
        }

    monkeypatch.setattr(durable_runs.engine, "stream", interrupted_stream)

    assert await durable_runs.execute_queued_run(descriptor.run_id, owner="pause-worker")

    factory = chat_db.get_session_factory()
    async with factory() as session:
        run = await session.get(ChatRun, descriptor.run_id)
        approval = await session.get(ChatToolApproval, (descriptor.run_id, "call-1"))
        assert run is not None
        events = await durable_runs.replay_events(session, run, after_seq=0)
    assert durable_runs._payload(run)["v2_max_tool_calls"] == 24
    assert run.status == "awaiting_input", [(event.type, event.payload.model_dump()) for event in events]
    assert approval is not None
    assert approval.arguments == "{}"
    assert approval.dispatch_hmac is not None
    assert decrypt_chat_content(approval.arguments_ciphertext or "") == '{"value":"change"}'
    assert approval.source == "custom_http"
    assert approval.effect == "external_mutation"
    assert approval.tool_definition_hash == "a" * 64
    assert approval.config_fingerprint == "b" * 64
    assert approval.destination_origin == "https://api.example.com"
    assert [event.type for event in events][-2:] == ["tool.approval_required", "run.stage.changed"]
    monkeypatch.setattr(durable_runs, "v2_runtime_ready", lambda _version: True)
    resolved = await durable_runs.resolve_tool_approval(
        run_id=descriptor.run_id,
        call_id="call-1",
        decision="approve",
        project_id="pause-project",
        user_id="pause-user",
    )
    assert resolved["run_status"] == "queued"
    async with factory() as session, session.begin():
        assert await durable_runs.claim_queued_run(session, descriptor.run_id, owner="resume-worker")
    assert await durable_runs._v2_approval_resume(run_id=descriptor.run_id, owner="resume-worker") == [
        {"call_id": "call-1", "decision": "approve"}
    ]


async def test_v2_duplicate_approval_interrupt_rolls_back_all_calls(
    chat_db, execution_snapshots, chat_checkpointer_db, monkeypatch
):
    from app.models.chat_runs import ChatToolApproval
    from app.services.chat import conversation_store as cs
    from app.services.chat import durable_runs

    monkeypatch.setattr(durable_runs, "is_supported", lambda version: version in {1, 2})
    monkeypatch.setattr(durable_runs, "SUPPORTED_EXECUTION_PROTOCOL_VERSIONS", {1, 2})

    capability_snapshot, pricing_snapshot = execution_snapshots
    conversation = await cs.create_conversation(
        project_id="duplicate-project",
        user_id="duplicate-user",
        title="Duplicate",
        model_name="m",
    )
    descriptor = await durable_runs.create_persistent_run(
        project_id="duplicate-project",
        user_id="duplicate-user",
        client_request_id="f30592c4-bc4c-467d-a85f-b3b0c35d315e",
        intent={
            "endpoint": "completion",
            "model_id": "m",
            "parts": [{"type": "text", "text": "mutate"}],
            "features": {},
        },
        conversation_id=conversation["id"],
        model_name="m",
        agent_id=None,
        user_content="mutate",
        user_parts=[{"type": "text", "text": "mutate"}],
        request_payload={
            "input_messages": [{"role": "user", "content": "mutate"}],
            "features": {"tool_policy": {"approval_mode": "required_for_mutations"}},
        },
        capability_snapshot=capability_snapshot,
        pricing_snapshot=pricing_snapshot,
        execution_protocol_version=2,
    )
    factory = chat_db.get_session_factory()
    async with factory() as session, session.begin():
        assert await durable_runs.claim_queued_run(session, descriptor.run_id, owner="duplicate-worker")

    call = {
        "call_id": "call-duplicate",
        "name": "custom__7__mutate_1",
        "arguments": '{"value":"change"}',
        "source": "custom_http",
        "effect": "external_mutation",
        "tool_definition_hash": "a" * 64,
        "config_fingerprint": "b" * 64,
        "destination_origin": "https://api.example.com",
    }
    with pytest.raises(durable_runs.DurableRunError, match="duplicate call IDs"):
        await durable_runs._persist_v2_approval_interrupt(
            run_id=descriptor.run_id,
            owner="duplicate-worker",
            calls=[call, dict(call)],
        )

    async with factory() as session:
        approvals = list(
            (
                await session.execute(select(ChatToolApproval).where(ChatToolApproval.run_id == descriptor.run_id))
            ).scalars()
        )
    assert approvals == []


async def test_mcp_oauth_refresh_replay_revokes_the_durable_family_and_grant(chat_db, monkeypatch):
    """A second refresh of the same token is a committed security transition, not a rollback."""
    from app.services.mcp_control_plane.oauth import hash_oauth_value, oauth_urls, pkce_s256
    from app.services.mcp_control_plane.oauth_authority import (
        McpOAuthAuthorityError,
        exchange_authorization_code,
        refresh_tokens,
    )

    monkeypatch.setattr(
        "app.services.mcp_control_plane.oauth_authority.get_settings",
        lambda: SimpleNamespace(mcp_access_token_ttl_seconds=900),
    )
    factory = chat_db.get_session_factory()
    now = datetime.now(UTC)
    code_verifier = "a" * 43
    urls = oauth_urls("https://api.example.test", production=True)
    async with factory() as session, session.begin():
        grant = McpDelegatedGrant(
            id="00000000-0000-0000-0000-000000000101",
            owner_user_id="mcp-user",
            owner_project_id="mcp-project",
            upstream_credential_name="afterglow-mcp-00000000-0000-0000-0000-000000000101",
            display_name="OAuth test",
            source="oauth",
            access_level="manage",
            status="active",
            application_credential_id="credential-a",
            credential_ciphertext="mcp-ac1:opaque",
            expires_at=now + timedelta(days=1),
            issued_at=now,
        )
        session.add_all(
            [
                grant,
                McpOAuthClient(
                    client_id="afterglow-dcr-test",
                    metadata_json={
                        "client_id": "afterglow-dcr-test",
                        "redirect_uris": ["https://client.example.test/callback"],
                        "grant_types": ["authorization_code", "refresh_token"],
                        "token_endpoint_auth_method": "none",
                    },
                    redirect_uris=["https://client.example.test/callback"],
                ),
                McpOAuthCode(
                    code_hash=hash_oauth_value("code-a"),
                    grant_id=grant.id,
                    client_id="afterglow-dcr-test",
                    redirect_uri="https://client.example.test/callback",
                    resource=urls.resource,
                    scopes=["mcp:read", "mcp:write"],
                    code_challenge=pkce_s256(code_verifier),
                    expires_at=now + timedelta(minutes=5),
                ),
            ]
        )

    initial = await exchange_authorization_code(
        factory,
        code="code-a",
        client_id="afterglow-dcr-test",
        redirect_uri="https://client.example.test/callback",
        resource=urls.resource,
        urls=urls,
        code_verifier=code_verifier,
    )
    rotated = await refresh_tokens(
        factory,
        refresh_token=initial.refresh_token,
        resource=urls.resource,
        urls=urls,
        scope=None,
    )
    assert rotated.refresh_token != initial.refresh_token

    with pytest.raises(McpOAuthAuthorityError, match="refresh token"):
        await refresh_tokens(
            factory,
            refresh_token=initial.refresh_token,
            resource=urls.resource,
            urls=urls,
            scope=None,
        )

    async with factory() as session:
        grant = await session.get(McpDelegatedGrant, "00000000-0000-0000-0000-000000000101")
        family = await session.scalar(select(McpOAuthTokenFamily).where(McpOAuthTokenFamily.grant_id == grant.id))
        tokens = (await session.scalars(select(McpOAuthToken).where(McpOAuthToken.family_id == family.id))).all()
    assert grant.status == "revoked"
    assert family.revoked_at is not None
    assert all(token.revoked_at is not None for token in tokens)


async def test_mcp_oauth_nonce_mismatch_commits_failure_and_blocks_replay(chat_db, monkeypatch):
    """A victim-browser callback consumes the attacker-created authorization request."""
    from app.services.chat import mcp_oauth as remote_oauth

    factory = chat_db.get_session_factory()
    state = "attacker-created-state"
    initiator_nonce = "a" * 43
    token_exchange_attempts = 0
    now = datetime.now(UTC)

    def unexpected_token_exchange():
        nonlocal token_exchange_attempts
        token_exchange_attempts += 1
        raise AssertionError("a rejected OAuth request must not reach the token endpoint")

    monkeypatch.setattr(
        remote_oauth,
        "_decrypt",
        lambda _encrypted_payload: {
            "initiator_nonce_hash": remote_oauth._hash(initiator_nonce),
            "callback_url": "https://console.example/api/v1/chat/mcp-oauth/callback",
            "client_id": "client-id",
            "code_verifier": "verifier",
            "resource": "https://mcp.example/mcp",
            "token_endpoint": "https://auth.example/token",
        },
    )
    monkeypatch.setattr(remote_oauth, "_http_client", unexpected_token_exchange)

    async with factory() as session, session.begin():
        session.add_all(
            [
                ChatMcpServer(
                    id=901,
                    scope="user",
                    owner_user_id="attacker",
                    owner_project_id="project-a",
                    name="Notion",
                    transport="http",
                    url="https://mcp.notion.com/mcp",
                    auth_mode="oauth",
                ),
                ChatMcpOAuthRequest(
                    id="00000000-0000-0000-0000-000000000901",
                    state_hash=remote_oauth._hash(state),
                    mcp_server_id=901,
                    owner_user_id="attacker",
                    owner_project_id="project-a",
                    encrypted_payload="opaque",
                    status="pending",
                    expires_at=now + timedelta(minutes=5),
                ),
            ]
        )

    with pytest.raises(remote_oauth.McpOAuthError, match="OAuth callback validation failed"):
        await remote_oauth.complete(
            state=state,
            code="victim-authorization-code",
            error=None,
            iss=None,
            initiator_nonce="victim-browser-nonce",
        )

    async with factory() as session:
        request = await session.get(ChatMcpOAuthRequest, "00000000-0000-0000-0000-000000000901")
    assert request.status == "failed"
    assert request.completed_at is not None

    with pytest.raises(remote_oauth.McpOAuthError, match="expired or was already used"):
        await remote_oauth.complete(
            state=state,
            code="replayed-authorization-code",
            error=None,
            iss=None,
            initiator_nonce=initiator_nonce,
        )
    assert token_exchange_attempts == 0


async def test_message_tree_marks_failed_user_run_retryable(chat_db):
    from app.services.chat import conversation_store as cs

    factory = chat_db.get_session_factory()
    conversation = await cs.create_conversation(
        user_id="retry-user",
        project_id="retry-project",
        title=None,
        model_name=None,
    )
    message = await cs.add_message(
        conversation["id"],
        role="user",
        content="다시 전송할 메시지",
        set_leaf=True,
    )
    async with factory() as session, session.begin():
        session.add(
            ChatRun(
                id="00000000-0000-0000-0000-000000000902",
                run_scope="persistent",
                conversation_id=conversation["id"],
                user_message_id=message["id"],
                project_id="retry-project",
                user_id="retry-user",
                model_name="test-model",
                capability_snapshot={},
                pricing_snapshot={},
                client_request_id="00000000-0000-0000-0000-000000000903",
                request_fingerprint="retryable-turn",
                fingerprint_version=1,
                last_seq=1,
                current_ordinal=0,
                status="failed",
            )
        )

    tree = await cs.list_message_tree(
        conversation["id"],
        user_id="retry-user",
        project_id="retry-project",
    )

    assert len(tree["messages"]) == 1
    assert tree["messages"][0]["id"] == message["id"]
    assert tree["messages"][0]["role"] == "user"
    assert tree["messages"][0]["execution"] == {
        "run_id": "00000000-0000-0000-0000-000000000902",
        "status": "failed",
        "retryable": True,
    }


async def test_mcp_oauth_cleanup_expires_and_reclaims_public_authority_rows(chat_db):
    factory = chat_db.get_session_factory()
    now = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    expired_grant_id = "00000000-0000-0000-0000-000000000950"
    stale_client_id = "00000000-0000-0000-0000-000000000951"
    revoked_client_id = "00000000-0000-0000-0000-000000000952"
    terminal_request_id = "00000000-0000-0000-0000-000000000953"
    pending_request_id = "00000000-0000-0000-0000-000000000954"

    async with factory() as session, session.begin():
        session.add_all(
            [
                McpDelegatedGrant(
                    id=expired_grant_id,
                    owner_user_id="mcp-owner",
                    owner_project_id="mcp-project",
                    upstream_credential_name="afterglow-mcp-expired",
                    display_name="Expired MCP grant",
                    source="personal_token",
                    access_level="read",
                    status="active",
                    application_credential_id="expired-upstream-credential",
                    credential_ciphertext="opaque-ciphertext",
                    credential_epoch=7,
                    issued_at=now - timedelta(days=1),
                    expires_at=now - timedelta(minutes=1),
                ),
                McpLumenSelection(
                    owner_user_id="mcp-owner",
                    owner_project_id="mcp-project",
                    grant_id=expired_grant_id,
                ),
                McpOAuthClient(
                    id=stale_client_id,
                    client_id="stale-public-client",
                    metadata_json={"client_name": "stale"},
                    redirect_uris=["http://127.0.0.1/callback"],
                    last_used_at=now - timedelta(days=91),
                ),
                McpOAuthClient(
                    id=revoked_client_id,
                    client_id="expired-revoked-client",
                    metadata_json={"client_name": "expired"},
                    redirect_uris=["http://127.0.0.1/callback"],
                    revoked_at=now - timedelta(days=91),
                ),
                McpOAuthAuthorizationRequest(
                    id=terminal_request_id,
                    ticket_hash="a" * 64,
                    client_id="terminal-client",
                    client_fingerprint="b" * 64,
                    redirect_uri="http://127.0.0.1/callback",
                    resource="https://mcp.example.test/api/v1/mcp",
                    scopes=["mcp:read"],
                    code_challenge="A" * 43,
                    status="approved",
                    expires_at=now - timedelta(days=2),
                ),
                McpOAuthAuthorizationRequest(
                    id=pending_request_id,
                    ticket_hash="c" * 64,
                    client_id="pending-client",
                    client_fingerprint="d" * 64,
                    redirect_uri="http://127.0.0.1/callback",
                    resource="https://mcp.example.test/api/v1/mcp",
                    scopes=["mcp:read"],
                    code_challenge="B" * 43,
                    status="pending",
                    expires_at=now - timedelta(hours=2),
                ),
            ]
        )

    counts = await sweep_delegated_authority(factory, now=now)

    assert counts.revoked_clients == 1
    assert counts.deleted_clients == 1
    assert counts.expired_tickets == 1
    assert counts.deleted_authorization_requests == 1
    assert counts.expired_grants == 1
    async with factory() as session:
        stale_client = await session.get(McpOAuthClient, stale_client_id)
        deleted_client = await session.get(McpOAuthClient, revoked_client_id)
        deleted_request = await session.get(McpOAuthAuthorizationRequest, terminal_request_id)
        expired_request = await session.get(McpOAuthAuthorizationRequest, pending_request_id)
        expired_grant = await session.get(McpDelegatedGrant, expired_grant_id)
        selection = await session.get(
            McpLumenSelection,
            {"owner_user_id": "mcp-owner", "owner_project_id": "mcp-project"},
        )

    assert stale_client is not None and stale_client.revoked_at is not None
    assert deleted_client is None
    assert deleted_request is None
    assert expired_request is not None and expired_request.status == "expired"
    assert expired_grant is not None
    assert expired_grant.status == "expired"
    assert expired_grant.credential_epoch == 8
    assert expired_grant.cleanup_pending is True
    assert expired_grant.application_credential_id == "expired-upstream-credential"
    assert expired_grant.credential_ciphertext == "opaque-ciphertext"
    assert selection is None


async def test_mcp_cleanup_reconciles_confirmed_deletion_after_late_dispatch_lease(chat_db, monkeypatch):
    """A lease that starts after Keystone deletion cannot leave stale local credentials."""
    from app.models.activity import ActivityLog
    from app.services.mcp_control_plane.authority import (
        confirm_keystone_cleanup,
        mark_expired_grants_for_cleanup,
    )

    factory = chat_db.get_session_factory()
    now = datetime.now(UTC)
    cleanup_grant_id = "00000000-0000-0000-0000-000000000955"
    expiry_grant_id = "00000000-0000-0000-0000-000000000956"
    async with factory() as session, session.begin():
        session.add_all(
            [
                McpDelegatedGrant(
                    id=cleanup_grant_id,
                    owner_user_id="cleanup-owner",
                    owner_project_id="cleanup-project",
                    upstream_credential_name="afterglow-mcp-cleanup",
                    display_name="Cleanup race",
                    source="personal_token",
                    access_level="read",
                    status="revoked",
                    application_credential_id="cleanup-credential",
                    credential_ciphertext="opaque-ciphertext",
                    cleanup_pending=True,
                    expires_at=now - timedelta(days=1),
                    revoked_at=now - timedelta(minutes=1),
                ),
                McpDelegatedGrant(
                    id=expiry_grant_id,
                    owner_user_id="expiry-owner",
                    owner_project_id="expiry-project",
                    upstream_credential_name="afterglow-mcp-expiry",
                    display_name="Expiry race",
                    source="personal_token",
                    access_level="read",
                    status="active",
                    expires_at=now - timedelta(minutes=1),
                ),
            ]
        )

    cleanup_started = Event()
    allow_cleanup_return = Event()
    cleanup_waits: list[bool] = []

    def confirm_absent(*_args, **_kwargs):
        cleanup_started.set()
        completed = allow_cleanup_return.wait(timeout=2)
        cleanup_waits.append(completed)
        return completed

    monkeypatch.setattr(
        "app.services.mcp_control_plane.authority.delete_and_confirm_application_credential",
        confirm_absent,
    )
    cleanup_task = asyncio.create_task(
        confirm_keystone_cleanup(
            factory,
            conn=SimpleNamespace(
                _afterglow_user_id="cleanup-owner",
                _afterglow_project_id="cleanup-project",
            ),
            grant_id=cleanup_grant_id,
            owner_user_id="cleanup-owner",
            owner_project_id="cleanup-project",
            username="cleanup-user",
            application_credential_id="cleanup-credential",
        )
    )
    try:
        assert await asyncio.to_thread(cleanup_started.wait, 2)
        async with factory() as session, session.begin():
            session.add(
                McpToolInvocation(
                    grant_id=cleanup_grant_id,
                    source="mcp",
                    tool_name="afterglow_vm_delete",
                    arguments_hash="a" * 64,
                    registry_version="1",
                    status="dispatch_authorized",
                    lease_expires_at=now + timedelta(minutes=1),
                )
            )
        allow_cleanup_return.set()
        assert await cleanup_task is True
        assert cleanup_waits == [True]
    finally:
        allow_cleanup_return.set()
        if not cleanup_task.done():
            await cleanup_task

    expiry_counts = await asyncio.gather(
        mark_expired_grants_for_cleanup(factory, now=now),
        mark_expired_grants_for_cleanup(factory, now=now),
    )
    assert sorted(expiry_counts) == [0, 1]

    async with factory() as session:
        cleanup_grant = await session.get(McpDelegatedGrant, cleanup_grant_id)
        expiry_grant = await session.get(McpDelegatedGrant, expiry_grant_id)
        cleanup_audit = await session.scalar(
            select(ActivityLog).where(
                ActivityLog.resource_id == cleanup_grant_id,
                ActivityLog.action == "mcp_grant.cleanup_confirmed",
            )
        )

    assert cleanup_grant is not None
    assert cleanup_grant.cleanup_pending is False
    assert cleanup_grant.application_credential_id is None
    assert cleanup_grant.credential_ciphertext is None
    assert cleanup_audit is not None
    assert cleanup_audit.extra["dispatch_lease_in_flight"] is True
    assert expiry_grant is not None
    assert expiry_grant.status == "expired"
    assert expiry_grant.credential_epoch == 2


async def test_mcp_authorize_and_revoke_serialize_before_cleanup(chat_db, monkeypatch):
    """A dispatch that owns the owner lock blocks revocation until its lease is durable."""
    from app.services.mcp_control_plane import authority as authority_service
    from app.services.mcp_control_plane import ledger as ledger_service
    from app.services.mcp_control_plane.authentication import McpPrincipal
    from app.services.mcp_control_plane.registry import entry_by_name

    factory = chat_db.get_session_factory()
    now = datetime.now(UTC)
    grant_id = "00000000-0000-0000-0000-000000000957"
    principal = McpPrincipal(
        grant_id=grant_id,
        user_id="race-owner",
        project_id="race-project",
        credential_epoch=1,
        scopes=frozenset(("mcp:read", "mcp:write")),
        source="personal_token",
    )
    async with factory() as session, session.begin():
        session.add(
            McpDelegatedGrant(
                id=grant_id,
                owner_user_id=principal.user_id,
                owner_project_id=principal.project_id,
                upstream_credential_name="afterglow-mcp-canonical-race",
                display_name="Canonical race",
                source="personal_token",
                access_level="manage",
                status="active",
                application_credential_id="canonical-race-credential",
                credential_ciphertext="opaque-ciphertext",
                expires_at=now + timedelta(days=1),
                issued_at=now,
            )
        )

    entry = entry_by_name("afterglow_vm_delete")
    assert entry is not None
    claim = await ledger_service.claim_mutation(
        principal,
        entry=entry,
        arguments={"server_id": "server-a"},
        idempotency_key="canonical-race-key",
    )

    authorization_has_lock = asyncio.Event()
    allow_authorization = asyncio.Event()
    revocation_lock_query_issued = asyncio.Event()
    original_ledger_lock = ledger_service.lock_owner

    async def hold_authorization_lock(session, *, owner_user_id, owner_project_id):
        row = await original_ledger_lock(
            session,
            owner_user_id=owner_user_id,
            owner_project_id=owner_project_id,
        )
        authorization_has_lock.set()
        await allow_authorization.wait()
        return row

    async def wait_for_revocation_lock(session, *, owner_user_id, owner_project_id):
        statement = (
            authority_service.select(McpOwnerLock)
            .where(
                McpOwnerLock.owner_user_id == owner_user_id,
                McpOwnerLock.owner_project_id == owner_project_id,
            )
            .with_for_update()
        )
        revocation_lock_query_issued.set()
        row = await session.scalar(statement)
        if row is None:
            raise authority_service.McpAuthorityError("MCP owner lock is unavailable")
        return row

    monkeypatch.setattr(ledger_service, "lock_owner", hold_authorization_lock)
    monkeypatch.setattr(authority_service, "lock_owner", wait_for_revocation_lock)

    authorization_task = asyncio.create_task(
        ledger_service.authorize_mutation_dispatch(principal, invocation_id=claim.invocation_id)
    )
    await asyncio.wait_for(authorization_has_lock.wait(), timeout=2)
    revocation_task = asyncio.create_task(
        authority_service.revoke_grant(
            factory,
            grant_id=grant_id,
            owner_user_id=principal.user_id,
            owner_project_id=principal.project_id,
            username="race-user",
        )
    )
    await asyncio.wait_for(revocation_lock_query_issued.wait(), timeout=2)
    assert not revocation_task.done()
    allow_authorization.set()
    assert await authorization_task is None
    assert await revocation_task == ("canonical-race-credential", False)

    monkeypatch.setattr(
        authority_service,
        "delete_and_confirm_application_credential",
        lambda *_args, **_kwargs: True,
    )
    cleanup_confirmed = await authority_service.confirm_keystone_cleanup(
        factory,
        conn=SimpleNamespace(
            _afterglow_user_id=principal.user_id,
            _afterglow_project_id=principal.project_id,
        ),
        grant_id=grant_id,
        owner_user_id=principal.user_id,
        owner_project_id=principal.project_id,
        username="race-user",
        application_credential_id="canonical-race-credential",
    )

    async with factory() as session:
        grant = await session.get(McpDelegatedGrant, grant_id)
        invocation = await session.get(McpToolInvocation, claim.invocation_id)

    assert cleanup_confirmed is False
    assert grant is not None
    assert grant.status == "revoked"
    assert grant.credential_epoch == 2
    assert grant.application_credential_id == "canonical-race-credential"
    assert grant.credential_ciphertext == "opaque-ciphertext"
    assert invocation is not None and invocation.status == "dispatch_authorized"


async def test_mcp_concurrent_cleanup_confirmation_is_idempotent(chat_db, monkeypatch):
    """Two confirmed external cleanups reconcile the same revoked grant once."""
    from app.services.mcp_control_plane.authority import confirm_keystone_cleanup

    factory = chat_db.get_session_factory()
    now = datetime.now(UTC)
    grant_id = "00000000-0000-0000-0000-000000000958"
    async with factory() as session, session.begin():
        session.add(
            McpDelegatedGrant(
                id=grant_id,
                owner_user_id="idempotent-owner",
                owner_project_id="idempotent-project",
                upstream_credential_name="afterglow-mcp-idempotent",
                display_name="Idempotent cleanup",
                source="personal_token",
                access_level="read",
                status="revoked",
                application_credential_id="idempotent-credential",
                credential_ciphertext="opaque-ciphertext",
                cleanup_pending=True,
                expires_at=now - timedelta(days=1),
                revoked_at=now - timedelta(minutes=1),
            )
        )

    external_barrier = Barrier(2, timeout=10)
    confirmations: list[str] = []

    def confirm_absent(*_args, **_kwargs):
        external_barrier.wait()
        confirmations.append("confirmed")
        return True

    monkeypatch.setattr(
        "app.services.mcp_control_plane.authority.delete_and_confirm_application_credential",
        confirm_absent,
    )
    conn = SimpleNamespace(
        _afterglow_user_id="idempotent-owner",
        _afterglow_project_id="idempotent-project",
    )
    results = await asyncio.gather(
        confirm_keystone_cleanup(
            factory,
            conn=conn,
            grant_id=grant_id,
            owner_user_id="idempotent-owner",
            owner_project_id="idempotent-project",
            username="idempotent-user",
            application_credential_id="idempotent-credential",
        ),
        confirm_keystone_cleanup(
            factory,
            conn=conn,
            grant_id=grant_id,
            owner_user_id="idempotent-owner",
            owner_project_id="idempotent-project",
            username="idempotent-user",
            application_credential_id="idempotent-credential",
        ),
    )

    async with factory() as session:
        grant = await session.get(McpDelegatedGrant, grant_id)

    assert results == [True, True]
    assert confirmations == ["confirmed", "confirmed"]
    assert grant is not None
    assert grant.cleanup_pending is False
    assert grant.application_credential_id is None
    assert grant.credential_ciphertext is None


async def test_mcp_concurrent_owner_lock_bootstrap_is_atomic(chat_db):
    """Concurrent first access creates one owner serialization row without deadlock."""
    from app.services.mcp_control_plane.authority import lock_owner

    factory = chat_db.get_session_factory()
    barrier = asyncio.Barrier(2)

    async def acquire_owner_lock():
        await barrier.wait()
        async with factory() as session, session.begin():
            row = await lock_owner(
                session,
                owner_user_id="bootstrap-owner",
                owner_project_id="bootstrap-project",
            )
            return row.lumen_selection_generation

    generations = await asyncio.gather(acquire_owner_lock(), acquire_owner_lock())
    async with factory() as session:
        rows = (
            await session.scalars(
                select(McpOwnerLock).where(
                    McpOwnerLock.owner_user_id == "bootstrap-owner",
                    McpOwnerLock.owner_project_id == "bootstrap-project",
                )
            )
        ).all()

    assert generations == [0, 0]
    assert len(rows) == 1
