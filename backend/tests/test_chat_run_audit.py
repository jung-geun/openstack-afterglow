from app.main import _AUDIT_PREFIX_MAP


def test_durable_chat_resources_are_fail_closed_audit_mapped():
    audit_map = dict(_AUDIT_PREFIX_MAP)

    assert audit_map["/api/v1/chat/runs"] == "chat_run"
    assert audit_map["/api/v1/chat/assets"] == "chat_asset"
    assert audit_map["/api/v1/chat/temp-threads"] == "chat_temp_thread"
