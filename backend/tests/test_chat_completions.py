import json

import pytest
from fastapi import HTTPException

from app.api.chat import completions
from app.models.chat_contracts import ChatFeatureOptions, ChatRunDescriptor, UserAssetInputPart
from app.services.chat import conversation_store as cs
from app.services.chat import credit, durable_runs
from app.services.chat import provider_store as ps

_BASE = "/api/v1/chat/conversations"
_HEADERS = {"Idempotency-Key": "d27ac16a-0e5b-465f-89cc-eefe6e9d0001"}


def _request(text: str = "hello", **extra):
    return {"parts": [{"type": "text", "text": text}], "model_id": "gpt-3.5-turbo", "features": {}, **extra}


async def test_selected_skills_are_loaded_only_from_owned_active_extensions(monkeypatch):
    async def fake_list(kind, **kwargs):
        assert kind == "skill"
        assert kwargs == {"user_id": "u1", "project_id": "p1", "active_only": True}
        return [
            {"id": 1, "name": "safe", "instructions": "first"},
            {"id": 2, "name": "unused", "instructions": "second"},
        ]

    monkeypatch.setattr(completions.es, "list_for_user", fake_list)
    assert await completions._load_skill_instructions(None, [1], "u1", "p1") == ["first"]
    assert await completions._load_skill_snapshot(None, [1], "u1", "p1") == (["first"], [{"id": 1, "name": "safe"}])


async def _ok_precheck(user_id, project_id=None):
    return None


def test_input_asset_failures_map_to_client_validation_error():
    assert completions._run_error(durable_runs.DurableRunInputError("input asset is not ready")).status_code == 422


def _conv():
    return {"id": "c1", "project_id": "test-project-123", "user_id": "test-user-123", "model_name": None}


def _resolved():
    return {
        "model_name": "gpt-3.5-turbo",
        "model_id": 1,
        "provider_name": "openai",
        "provider_id": 1,
        "config_version_hash": "a" * 64,
        "margin_multiplier": "1",
        "input_price_per_token": "0.000001",
        "output_price_per_token": "0.000002",
    }


async def _patch_text_execution(monkeypatch):
    monkeypatch.setattr(credit, "precheck", _ok_precheck)
    monkeypatch.setattr(cs, "get_conversation", lambda *args, **kwargs: _return(_conv()))
    monkeypatch.setattr(
        cs, "get_active_path", lambda *args, **kwargs: _return({"messages": [], "active_leaf_id": None})
    )
    monkeypatch.setattr(cs, "add_message", lambda *args, **kwargs: _return({"id": 1}))
    monkeypatch.setattr(ps, "resolve_model", lambda *args, **kwargs: _return(_resolved()))
    monkeypatch.setattr(durable_runs, "existing_run_for_intent", lambda *args, **kwargs: _return(None))


async def _return(value):
    return value


class TestReasoningEffortValidation:
    def test_auto_and_none_are_supported_for_reasoning_models(self):
        resolved = {"capabilities": {"reasoning": True, "reasoning_options": [{"type": "toggle"}]}}
        assert completions._validated_reasoning_effort("auto", resolved) == "auto"
        assert completions._validated_reasoning_effort("none", resolved) == "none"

    def test_only_models_dev_effort_values_are_allowed(self):
        resolved = {
            "capabilities": {
                "reasoning": True,
                "reasoning_options": [{"type": "effort", "values": ["low", "xhigh", "max", "ultra"]}],
            }
        }
        assert completions._validated_reasoning_effort("ultra", resolved) == "ultra"
        with pytest.raises(HTTPException, match="지원하지 않습니다"):
            completions._validated_reasoning_effort("high", resolved)

    def test_unlisted_effort_is_rejected_for_toggle_only_models(self):
        resolved = {"capabilities": {"reasoning": True, "reasoning_options": [{"type": "toggle"}]}}
        with pytest.raises(HTTPException, match="지원하지 않습니다"):
            completions._validated_reasoning_effort("low", resolved)


class TestExecutionCapabilityGate:
    def test_rejects_feature_without_priced_execution_route(self):
        features = ChatFeatureOptions(web_search={"enabled": True, "provider_id": 7})
        resolved = {
            "input_price_per_token": "0.000001",
            "output_price_per_token": "0.000002",
            "capabilities": {
                "feature_gates": {
                    "text": {"available": True, "pricing_available": True},
                    "web_search": {
                        "available": True,
                        "pricing_available": False,
                        "reason_code": "pricing_unavailable",
                    },
                }
            },
        }

        with pytest.raises(HTTPException, match="web_search"):
            completions._require_execution_capability(features, resolved)

    def test_accepts_priced_managed_web_search_and_fetch(self):
        features = ChatFeatureOptions(
            web_search={"enabled": True, "provider_id": 7},
            web_fetch={"enabled": True},
        )
        resolved = {
            "input_price_per_token": "0.000001",
            "output_price_per_token": "0.000002",
            "capabilities": {
                "feature_gates": {
                    "text": {"available": True, "pricing_available": True},
                    "web_search": {"available": True, "mode": "managed", "pricing_available": True},
                    "web_fetch": {"available": True, "mode": "managed", "pricing_available": True},
                }
            },
        }

        completions._require_execution_capability(features, resolved)

    def test_accepts_priced_user_selected_advisor_with_function_calling_executor(self):
        features = ChatFeatureOptions(advisor={"enabled": True, "model_id": 9})
        resolved = {
            "input_price_per_token": "0.000001",
            "output_price_per_token": "0.000002",
            "capabilities": {
                "function_calling": True,
                "feature_gates": {"text": {"available": True, "pricing_available": True}},
            },
        }
        routes = {
            "advisor": {
                "provider_id": 7,
                "model_id": 9,
                "input_price_per_token": "0.0003",
                "output_price_per_token": "0.0004",
            }
        }

        completions._require_execution_capability(features, resolved, feature_routes=routes)

    def test_rejects_managed_feature_when_tools_are_disabled(self):
        features = ChatFeatureOptions(
            web_fetch={"enabled": True},
            tool_policy={"mode": "none"},
        )
        resolved = {
            "input_price_per_token": "0.000001",
            "output_price_per_token": "0.000002",
            "capabilities": {
                "feature_gates": {
                    "text": {"available": True, "pricing_available": True},
                    "web_fetch": {"available": True, "pricing_available": True},
                }
            },
        }

        with pytest.raises(HTTPException, match="requires tool execution"):
            completions._require_execution_capability(features, resolved)

    def test_accepts_priced_text_when_legacy_override_has_no_canonical_gates(self):
        completions._require_execution_capability(
            ChatFeatureOptions(),
            {"input_price_per_token": "0.000001", "output_price_per_token": "0.000002", "capabilities": {}},
        )

    def test_rejects_unpriced_text_execution(self):
        with pytest.raises(HTTPException, match="text"):
            completions._require_execution_capability(ChatFeatureOptions(), {"capabilities": {}})

    def test_accepts_manual_memory_until_semantic_retrieval_is_enabled(self):
        completions._require_execution_capability(
            ChatFeatureOptions(memory=True),
            {"input_price_per_token": "0.000001", "output_price_per_token": "0.000002", "capabilities": {}},
        )

    def test_rejects_unavailable_input_modality(self):
        image = UserAssetInputPart(type="image", asset_id="asset-1")
        with pytest.raises(HTTPException, match="image_input"):
            completions._require_execution_capability(
                ChatFeatureOptions(),
                {"input_price_per_token": "0.000001", "output_price_per_token": "0.000002", "capabilities": {}},
                parts=[image],
            )

    async def test_disabled_memory_never_loads_user_memory(self, monkeypatch):
        async def fail_memory_lookup(**_kwargs):
            raise AssertionError("memory store must not be queried")

        monkeypatch.setattr(
            completions.ws, "get_instructions_for_run", lambda *_args, **_kwargs: _return("workspace rule")
        )
        monkeypatch.setattr(completions.ms, "active_contents_for_run", fail_memory_lookup)

        workspace, memories = await completions._load_context({"workspace_id": 7}, "u1", "p1", include_memory=False)

        assert workspace == "workspace rule"
        assert memories == []

    def test_run_snapshot_excludes_provider_secret(self):
        capabilities, pricing = completions._run_snapshots(
            {
                "model_name": "model-a",
                "capabilities": {"feature_gates": {}},
                "input_price_per_token": "0.000001",
                "output_price_per_token": "0.000002",
                "model_id": 1,
                "provider_id": 1,
                "config_version_hash": "a" * 64,
                "margin_multiplier": "1",
                "price_source": "models.dev",
                "provider_name": "provider-a",
                "api_key": "must-not-persist",
            },
            {"memory": True},
            feature_routes={
                "search": {
                    "provider_id": 2,
                    "provider_name": "search-provider",
                    "config_version_hash": "b" * 64,
                    "api_key": "must-not-persist",
                    "api_base": "https://search.example",
                },
                "advisor": {
                    "provider_id": 3,
                    "provider_name": "advisor-provider",
                    "model_id": 4,
                    "model_name": "advisor-model",
                    "config_version_hash": "c" * 64,
                    "input_price_per_token": "0.0003",
                    "output_price_per_token": "0.0004",
                    "api_key": "must-not-persist",
                },
            },
        )

        assert "api_key" not in capabilities
        assert "api_key" not in pricing
        assert capabilities["feature_routes"]["search"] == {
            "provider_id": 2,
            "provider_name": "search-provider",
            "config_version_hash": "b" * 64,
        }
        assert pricing["input_price_per_token"] == "0.000001"
        assert "must-not-persist" not in json.dumps(capabilities)
        assert pricing["component_prices"]["advisor_input_price_per_token"] == "0.0003"
        assert pricing["component_prices"]["advisor_output_price_per_token"] == "0.0004"

    async def test_resolves_only_user_selected_feature_routes(self, monkeypatch):
        search_route = {"provider_id": 7, "provider_name": "search", "config_version_hash": "s" * 64}
        advisor_route = {
            "provider_id": 8,
            "provider_name": "advisor",
            "model_id": 9,
            "model_name": "advisor-model",
            "config_version_hash": "a" * 64,
        }
        monkeypatch.setattr(completions.ps, "get_active_provider_route", lambda provider_id: _return(search_route))
        monkeypatch.setattr(completions.ps, "resolve_model_by_id", lambda model_id: _return(advisor_route))

        routes = await completions._resolve_feature_routes(
            ChatFeatureOptions(
                web_search={"enabled": True, "provider_id": 7},
                advisor={"enabled": True, "model_id": 9},
            )
        )

        assert routes == {"search": search_route, "advisor": advisor_route}

    async def test_rejects_unavailable_selected_feature_route(self, monkeypatch):
        monkeypatch.setattr(completions.ps, "get_active_provider_route", lambda provider_id: _return(None))
        with pytest.raises(HTTPException, match="selected web search provider"):
            await completions._resolve_feature_routes(
                ChatFeatureOptions(web_search={"enabled": True, "provider_id": 7})
            )

    async def test_enabled_manual_memory_is_loaded(self, monkeypatch):
        captured = {}

        async def load_memory(**kwargs):
            captured.update(kwargs)
            return ["사용자는 Python을 선호합니다."]

        monkeypatch.setattr(completions.ws, "get_instructions_for_run", lambda *_args, **_kwargs: _return(None))
        monkeypatch.setattr(completions.ms, "active_contents_for_run", load_memory)

        workspace, memories = await completions._load_context({"workspace_id": None}, "u1", "p1", include_memory=True)

        assert workspace is None
        assert memories == ["사용자는 Python을 선호합니다."]
        assert captured == {"user_id": "u1", "project_id": "p1", "workspace_id": None}


class TestActiveRunRecovery:
    async def test_active_run_descriptor_is_available_after_client_disconnect(self, client, monkeypatch):
        monkeypatch.setattr(cs, "get_conversation", lambda *args, **kwargs: _return(_conv()))
        descriptor = ChatRunDescriptor(
            run_id="run-active",
            status="running",
            events_url="/api/v1/chat/runs/run-active/events",
            cancel_url="/api/v1/chat/runs/run-active/cancel",
        )
        monkeypatch.setattr(
            durable_runs,
            "active_run_descriptors",
            lambda **_kwargs: _return([descriptor]),
        )

        response = await client.get(f"{_BASE}/c1/runs?active=true")

        assert response.status_code == 200
        assert response.json() == [descriptor.model_dump(mode="json")]

    async def test_owner_active_run_snapshot_includes_conversation_id(self, client, monkeypatch):
        descriptor = ChatRunDescriptor(
            run_id="run-active",
            conversation_id="c1",
            status="running",
            events_url="/api/v1/chat/runs/run-active/events",
            cancel_url="/api/v1/chat/runs/run-active/cancel",
        )
        monkeypatch.setattr(
            durable_runs,
            "active_run_descriptors_for_owner",
            lambda **_kwargs: _return([descriptor]),
        )

        response = await client.get("/api/v1/chat/runs?active=true")

        assert response.status_code == 200
        assert response.json() == [descriptor.model_dump(mode="json")]


class TestCanonicalCompletionRequests:
    async def test_legacy_message_payload_is_rejected(self, client):
        response = await client.post(
            f"{_BASE}/c1/completions",
            headers=_HEADERS,
            json={"message": "legacy", "model": "gpt-3.5-turbo"},
        )
        assert response.status_code == 422

    async def test_quota_is_checked_after_canonical_body_validation(self, client, monkeypatch):
        async def reject(*_args, **_kwargs):
            raise credit.QuotaExceeded("quota exhausted")

        monkeypatch.setattr(credit, "precheck", reject)
        monkeypatch.setattr(durable_runs, "existing_run_for_intent", lambda **_kwargs: _return(None))
        monkeypatch.setattr(completions, "_load_owned_conv", lambda *_args, **_kwargs: _return({}))
        monkeypatch.setattr(
            cs, "get_active_path", lambda *_args, **_kwargs: _return({"active_leaf_id": None, "messages": []})
        )
        response = await client.post(f"{_BASE}/c1/completions", headers=_HEADERS, json=_request())
        assert response.status_code == 402

    async def test_text_parts_create_durable_descriptor_without_provider_call(self, client, monkeypatch):
        await _patch_text_execution(monkeypatch)
        seen = {}

        async def create_persistent_run(**kwargs):
            seen.update(kwargs)
            return ChatRunDescriptor(
                run_id="run-1",
                status="queued",
                events_url="/api/v1/chat/runs/run-1/events",
                cancel_url="/api/v1/chat/runs/run-1/cancel",
            )

        monkeypatch.setattr(durable_runs, "create_persistent_run", create_persistent_run)
        response = await client.post(f"{_BASE}/c1/completions", headers=_HEADERS, json=_request("first"))

        assert response.status_code == 202
        assert response.json()["run_id"] == "run-1"
        assert seen["request_payload"]["input_messages"][-1] == {"role": "user", "content": "first"}
        assert seen["intent"]["parts"] == [{"type": "text", "text": "first"}]

    async def test_same_idempotency_key_returns_existing_before_user_message_write(self, client, monkeypatch):
        await _patch_text_execution(monkeypatch)
        existing = ChatRunDescriptor(
            run_id="run-existing",
            status="queued",
            events_url="/api/v1/chat/runs/run-existing/events",
            cancel_url="/api/v1/chat/runs/run-existing/cancel",
        )
        monkeypatch.setattr(durable_runs, "existing_run_for_intent", lambda *args, **kwargs: _return(existing))

        async def unavailable_model(*_args, **_kwargs):
            raise AssertionError("retry must not resolve a mutable model route")

        monkeypatch.setattr(completions, "_resolve_model", unavailable_model)

        async def unexpected_message(*_args, **_kwargs):
            raise AssertionError("retry must not create another user message")

        monkeypatch.setattr(cs, "add_message", unexpected_message)
        response = await client.post(f"{_BASE}/c1/completions", headers=_HEADERS, json=_request("first"))

        assert response.status_code == 202
        assert response.json()["run_id"] == "run-existing"

    async def test_asset_parts_are_rejected_until_asset_execution_exists(self, client, monkeypatch):
        await _patch_text_execution(monkeypatch)
        response = await client.post(
            f"{_BASE}/c1/completions",
            headers=_HEADERS,
            json={"parts": [{"type": "image", "asset_id": "asset-1"}], "model_id": "gpt-3.5-turbo", "features": {}},
        )
        assert response.status_code == 422
        assert "image" in response.json()["detail"]

    async def test_clean_image_part_enters_durable_request_payload(self, client, monkeypatch):
        await _patch_text_execution(monkeypatch)
        resolved = {
            **_resolved(),
            "capabilities": {
                "vision": True,
                "feature_gates": {
                    "text": {"available": True, "pricing_available": True},
                    "image_input": {"available": True, "pricing_available": True},
                },
            },
        }
        monkeypatch.setattr(ps, "resolve_model", lambda *args, **kwargs: _return(resolved))
        seen = {}

        async def create_persistent_run(**kwargs):
            seen.update(kwargs)
            return ChatRunDescriptor(
                run_id="run-image",
                status="queued",
                events_url="/api/v1/chat/runs/run-image/events",
                cancel_url="/api/v1/chat/runs/run-image/cancel",
            )

        monkeypatch.setattr(durable_runs, "create_persistent_run", create_persistent_run)
        response = await client.post(
            f"{_BASE}/c1/completions",
            headers=_HEADERS,
            json={
                "parts": [
                    {"type": "text", "text": "describe"},
                    {"type": "image", "asset_id": "f6d18ec7-c8d8-4db8-9bd7-2dceb0f0f68e"},
                ],
                "model_id": "gpt-3.5-turbo",
                "features": {},
            },
        )

        assert response.status_code == 202
        assert seen["user_parts"][1]["asset_id"] == "f6d18ec7-c8d8-4db8-9bd7-2dceb0f0f68e"
        assert seen["request_payload"]["input_parts"] == seen["user_parts"]

    async def test_regenerate_requires_canonical_model_and_feature_options(self, client):
        response = await client.post(
            f"{_BASE}/c1/messages/1/regenerate",
            headers=_HEADERS,
            json={"model": "gpt-3.5-turbo"},
        )
        assert response.status_code == 422


class TestCanonicalTempCompletion:
    async def test_temp_completion_creates_thread_and_descriptor(self, client, monkeypatch):
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        monkeypatch.setattr(ps, "resolve_model", lambda *args, **kwargs: _return(_resolved()))
        monkeypatch.setattr(durable_runs, "existing_run_for_intent", lambda **_kwargs: _return(None))
        seen = {}

        async def create_temp_run(**kwargs):
            seen.update(kwargs)
            return ChatRunDescriptor(
                run_id="run-temp",
                temp_thread_id="thread-1",
                status="queued",
                events_url="/api/v1/chat/runs/run-temp/events",
                cancel_url="/api/v1/chat/runs/run-temp/cancel",
            )

        monkeypatch.setattr(durable_runs, "create_temp_run", create_temp_run)
        response = await client.post(
            "/api/v1/chat/temp-completions",
            headers=_HEADERS,
            json={"parts": [{"type": "text", "text": "temporary"}], "model_id": "gpt-3.5-turbo", "features": {}},
        )
        assert response.status_code == 202
        assert seen["temp_thread_id"] is None
        assert seen["request_payload"]["input_messages"] == [{"role": "user", "content": "temporary"}]
