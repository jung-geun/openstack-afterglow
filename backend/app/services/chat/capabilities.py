"""Canonical, fail-closed model capability detection.

Provider-specific SDK probes are normalized here.  Callers must gate a requested
feature on the returned availability rather than silently dropping parameters.
"""

from __future__ import annotations

from typing import Any


def _probe(name: str, *, model_name: str, provider_type: str | None) -> bool:
    try:
        import litellm

        probe = getattr(litellm, name)
        try:
            return bool(probe(model=model_name, custom_llm_provider=provider_type))
        except TypeError:
            try:
                return bool(probe(model=model_name))
            except TypeError:
                return bool(probe(model_name))
    except Exception:
        return False


def litellm_capabilities(model_name: str, provider_type: str | None) -> dict[str, Any]:
    """Return the legacy display fields plus canonical feature gates.

    LiteLLM cannot infer managed routes or pricing, so those are deliberately
    unavailable rather than guessed.
    """
    vision = _probe("supports_vision", model_name=model_name, provider_type=provider_type)
    pdf_input = _probe("supports_pdf_input", model_name=model_name, provider_type=provider_type)
    reasoning = _probe("supports_reasoning", model_name=model_name, provider_type=provider_type)
    function_calling = _probe("supports_function_calling", model_name=model_name, provider_type=provider_type)
    structured_output = _probe("supports_response_schema", model_name=model_name, provider_type=provider_type)
    return {
        # Existing model-admin/UI fields retained until the capability API is cut over.
        "vision": vision,
        "reasoning": reasoning,
        "tool_call": function_calling,
        "attachment": vision or pdf_input,
        "modalities": None,
        "reasoning_options": [],
        "context_limit": None,
        # Canonical gate contract.
        "streaming": True,
        "function_calling": function_calling,
        "parallel_function_calling": False,
        "structured_output": structured_output,
        "web_search": False,
        "web_fetch": False,
        "advisor": False,
        "responses_api": False,
        "mcp": False,
        "code_interpreter": False,
        "computer_use": False,
        "endpoints": ["chat_completions"],
        "input_modalities": ["text", *(["image"] if vision else []), *(["pdf"] if pdf_input else [])],
        "output_modalities": ["text"],
        "allowed_output_combinations": [["text"]],
        "media_options": {},
        "feature_gates": {
            "text": {"available": True, "mode": "native", "reason_code": None, "pricing_available": True},
            "structured_output": {
                "available": structured_output,
                "mode": "native" if structured_output else "none",
                "reason_code": None if structured_output else "provider_unsupported",
                "pricing_available": structured_output,
            },
            "web_search": {
                "available": False,
                "mode": "none",
                "reason_code": "provider_unsupported",
                "pricing_available": False,
            },
            "web_fetch": {
                "available": False,
                "mode": "none",
                "reason_code": "provider_unsupported",
                "pricing_available": False,
            },
            "advisor": {
                "available": False,
                "mode": "none",
                "reason_code": "not_configured",
                "pricing_available": False,
            },
            "memory": {"available": True, "mode": "native", "reason_code": None, "pricing_available": True},
            "image_input": {
                "available": vision,
                "mode": "native" if vision else "none",
                "reason_code": None if vision else "provider_unsupported",
                "pricing_available": vision,
            },
            "document_input": {
                "available": pdf_input,
                "mode": "native" if pdf_input else "none",
                "reason_code": None if pdf_input else "provider_unsupported",
                "pricing_available": pdf_input,
            },
            "audio_input": {
                "available": False,
                "mode": "none",
                "reason_code": "route_unavailable",
                "pricing_available": False,
            },
            "video_input": {
                "available": False,
                "mode": "none",
                "reason_code": "route_unavailable",
                "pricing_available": False,
            },
            "image_output": {
                "available": False,
                "mode": "none",
                "reason_code": "route_unavailable",
                "pricing_available": False,
            },
            "audio_output": {
                "available": False,
                "mode": "none",
                "reason_code": "route_unavailable",
                "pricing_available": False,
            },
            "video_output": {
                "available": False,
                "mode": "none",
                "reason_code": "route_unavailable",
                "pricing_available": False,
            },
            "mcp": {"available": False, "mode": "none", "reason_code": "not_configured", "pricing_available": False},
            "approval_tools": {
                "available": False,
                "mode": "none",
                "reason_code": "checkpointer_unavailable",
                "pricing_available": False,
            },
            "code_interpreter": {
                "available": False,
                "mode": "none",
                "reason_code": "sandbox_unavailable",
                "pricing_available": False,
            },
            "computer_use": {
                "available": False,
                "mode": "none",
                "reason_code": "sandbox_unavailable",
                "pricing_available": False,
            },
        },
    }


def normalize_capabilities(stored: dict[str, Any] | None, detected: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy models.dev/override shapes to canonical feature gates."""
    if not stored:
        return detected
    normalized = dict(detected)
    normalized.update({key: value for key, value in stored.items() if key != "feature_gates"})
    gates = {name: dict(gate) for name, gate in detected["feature_gates"].items()}
    stored_gates = stored.get("feature_gates")
    if isinstance(stored_gates, dict):
        for name, gate in stored_gates.items():
            if isinstance(gate, dict) and name in gates:
                gates[name].update(gate)

    legacy_modalities = stored.get("modalities")
    if isinstance(legacy_modalities, dict):
        inputs = legacy_modalities.get("input") if isinstance(legacy_modalities.get("input"), list) else []
        outputs = legacy_modalities.get("output") if isinstance(legacy_modalities.get("output"), list) else []
    else:
        inputs = normalized.get("input_modalities") or []
    legacy_vision_specified = "vision" in stored or isinstance(legacy_modalities, dict)
    if legacy_vision_specified:
        vision = bool(stored.get("vision", normalized.get("vision"))) or "image" in inputs
        normalized["vision"] = vision
        gates["image_input"] = {
            **gates["image_input"],
            "available": vision,
            "mode": "native" if vision else "none",
            "reason_code": None if vision else "provider_unsupported",
        }
    legacy_pdf_specified = isinstance(legacy_modalities, dict)
    if legacy_pdf_specified:
        pdf_input = "pdf" in inputs
        gates["document_input"] = {
            **gates["document_input"],
            "available": pdf_input,
            "mode": "native" if pdf_input else "none",
            "reason_code": None if pdf_input else "provider_unsupported",
        }
    if "tool_call" in stored:
        normalized["function_calling"] = bool(stored["tool_call"])
    elif "function_calling" in stored:
        normalized["function_calling"] = bool(stored["function_calling"])
    if isinstance(legacy_modalities, dict):
        normalized["input_modalities"] = list(inputs)
        normalized["output_modalities"] = list(outputs)
        for modality in ("image", "audio", "video"):
            gate = f"{modality}_output"
            gates[gate] = {
                **gates[gate],
                "available": modality in outputs,
                "mode": "native" if modality in outputs else "none",
                "reason_code": None if modality in outputs else "provider_unsupported",
            }
    normalized["feature_gates"] = gates
    return normalized
