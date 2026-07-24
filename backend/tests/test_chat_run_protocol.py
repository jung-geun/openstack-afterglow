from decimal import Decimal

from app.config import get_settings
from app.models.chat_contracts import validate_chat_run_event
from app.services.chat import durable_runs
from app.services.chat.durable_runs import _fingerprint


def test_idempotency_fingerprint_normalizes_feature_domain_order():
    base = {
        "endpoint": "completion",
        "features": {
            "web_search": {"allowed_domains": ["b.example", "a.example"], "blocked_domains": []},
            "web_fetch": {"allowed_domains": [], "blocked_domains": ["z.example", "y.example"]},
        },
    }
    reordered = {
        "endpoint": "completion",
        "features": {
            "web_search": {"allowed_domains": ["a.example", "b.example"], "blocked_domains": []},
            "web_fetch": {"allowed_domains": [], "blocked_domains": ["y.example", "z.example"]},
        },
    }
    assert _fingerprint(base) == _fingerprint(reordered)


def test_managed_usage_components_use_frozen_component_prices():
    cost, components = durable_runs._managed_usage_components(
        [
            {
                "kind": "web_search_requests",
                "price_key": "web_search_request_per_unit",
                "quantity": "1",
                "unit": "request",
                "source": "search",
            },
            {
                "kind": "web_fetch_context",
                "price_key": "web_fetch_context_per_unit",
                "quantity": "1",
                "unit": "context",
                "source": "fetch",
            },
        ],
        pricing_snapshot={
            "component_prices": {
                "web_search_request_per_unit": "0.002",
                "web_fetch_context_per_unit": "0.003",
            }
        },
        model_name="executor",
    )

    assert cost == Decimal("0.0050000000")
    assert [component["cost_usd"] for component in components] == ["0.0020000000", "0.0030000000"]


def test_advisor_usage_uses_its_immutable_route_price():
    cost, components = durable_runs._managed_usage_components(
        [
            {
                "kind": "advisor_input_tokens",
                "price_key": "advisor_input_price_per_token",
                "quantity": "10",
                "unit": "token",
                "source": "advisor",
                "model_name": "advisor-model",
            },
            {
                "kind": "advisor_output_tokens",
                "price_key": "advisor_output_price_per_token",
                "quantity": "5",
                "unit": "token",
                "source": "advisor",
                "model_name": "advisor-model",
            },
        ],
        pricing_snapshot={
            "component_prices": {
                "advisor_input_price_per_token": "0.0001",
                "advisor_output_price_per_token": "0.0002",
            }
        },
        model_name="executor",
    )

    assert cost == Decimal("0.0020000000")
    assert [component["model_name"] for component in components] == ["advisor-model", "advisor-model"]


async def test_completion_and_event_preflight_allow_durable_headers(client):
    origin = get_settings().cors_origin_list[0]
    for path, requested_header in (
        ("/api/v1/chat/conversations/c1/completions", "Idempotency-Key"),
        ("/api/v1/chat/runs/run-1/events", "Last-Event-ID"),
    ):
        response = await client.options(
            path,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST" if "completions" in path else "GET",
                "Access-Control-Request-Headers": requested_header,
            },
        )
        assert response.status_code == 200
        assert requested_header.lower() in response.headers["Access-Control-Allow-Headers"].lower()


async def test_events_replay_canonical_journal_with_sse_id(client, monkeypatch):
    event = validate_chat_run_event(
        {
            "event_id": "run-1:1",
            "run_id": "run-1",
            "seq": 1,
            "type": "run.completed",
            "created_at": "2026-07-21T00:00:00Z",
            "payload": {"status": "completed", "message_id": "42"},
        }
    )

    async def events(**kwargs):
        assert kwargs["after_seq"] == 0
        return [event], True

    monkeypatch.setattr(durable_runs, "owned_events", events)
    response = await client.get("/api/v1/chat/runs/run-1/events")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert "id: run-1:1" in response.text
    assert "event: run.completed" in response.text
    assert '"message_id": "42"' in response.text


async def test_events_reject_mismatched_cursor_sources(client):
    response = await client.get(
        "/api/v1/chat/runs/run-1/events?after_seq=2",
        headers={"Last-Event-ID": "run-1:1"},
    )
    assert response.status_code == 400


async def test_events_return_gone_after_temporary_journal_purge(client, monkeypatch):
    async def events(**kwargs):
        raise durable_runs.DurableRunCursorExpired("temporary chat event journal has expired")

    monkeypatch.setattr(durable_runs, "owned_events", events)
    response = await client.get("/api/v1/chat/runs/run-1/events", headers={"Last-Event-ID": "run-1:1"})

    assert response.status_code == 410


async def test_cancel_is_owner_scoped_and_idempotent(client, monkeypatch):
    seen = {}

    async def cancel(**kwargs):
        seen.update(kwargs)
        return {"run_id": "run-1", "status": "running"}

    monkeypatch.setattr(durable_runs, "request_cancelled", cancel)
    response = await client.post("/api/v1/chat/runs/run-1/cancel")

    assert response.status_code == 200
    assert seen["run_id"] == "run-1"
    assert seen["project_id"] == "test-project-123"
    assert seen["user_id"] == "test-user-123"
