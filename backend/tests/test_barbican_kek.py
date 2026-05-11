"""PR2 회귀 테스트 — per-project KEK auto-provisioning (barbican.ensure_project_kek).

설계 원칙:
- per-project KEK (per-cluster 아님) — 같은 project 의 cluster 들이 KEK 공유
- 발급자 = manager user (이미 § 28 의 ensure_cluster_manager_user) — 같은 user 의
  app cred 가 자동으로 read 권한 (Barbican default policy: creator 접근)
- idempotent: 이름 'afterglow-k8s-kek' 으로 검색 → ACTIVE 면 재사용, 없으면 신규 발급
"""

from unittest.mock import MagicMock, patch

import pytest


def _mock_settings():
    s = MagicMock()
    s.os_auth_url = "https://keystone.example.com:5000/v3"
    s.os_user_domain_name = "Default"
    s.os_project_domain_name = "Default"
    s.os_region_name = "RegionOne"
    s.os_interface = "public"
    s.ssl_verify = True
    return s


def _mock_secrets_response(secrets: list[dict]) -> MagicMock:
    r = MagicMock()
    r.json.return_value = {"secrets": secrets}
    return r


def _mock_order_create_response(order_ref: str = "https://barbican.example/v1/orders/order-1") -> MagicMock:
    r = MagicMock()
    r.status_code = 202
    r.json.return_value = {"order_ref": order_ref}
    r.raise_for_status = MagicMock()
    return r


def _mock_order_get_response(
    status: str, secret_ref: str = "https://barbican.example/v1/secrets/kek-uuid-new"
) -> MagicMock:
    r = MagicMock()
    r.json.return_value = {"status": status, "secret_ref": secret_ref}
    return r


def test_ensure_project_kek_reuses_existing_active_kek():
    """기존 ACTIVE KEK 가 있으면 그 UUID 를 재사용 (idempotent)."""
    import asyncio

    from app.services import barbican

    fake_conn = MagicMock()
    fake_conn.session.get_endpoint.return_value = "https://barbican.example"
    fake_conn.session.get.return_value = _mock_secrets_response(
        [
            {
                "secret_ref": "https://barbican.example/v1/secrets/existing-kek-uuid",
                "name": "afterglow-k8s-kek",
                "status": "ACTIVE",
            }
        ]
    )

    with (
        patch("app.services.keystone.ensure_cluster_manager_user") as mock_ensure_user,
        patch("app.services.keystone._connect_as_manager", return_value=fake_conn),
    ):

        async def _fake_ensure(_):
            return ("user-id", "password")

        mock_ensure_user.side_effect = _fake_ensure
        kek_id = asyncio.run(barbican.ensure_project_kek("proj-test"))

    assert kek_id == "existing-kek-uuid"
    fake_conn.close.assert_called_once()


def test_ensure_project_kek_creates_when_missing():
    """KEK 없으면 order create + ACTIVE 폴링 후 신규 UUID 반환."""
    import asyncio

    from app.services import barbican

    fake_conn = MagicMock()
    fake_conn.session.get_endpoint.return_value = "https://barbican.example"
    # 1차 호출: secret 검색 (빈 결과)
    # 2차 호출: order GET (ACTIVE)
    fake_conn.session.get.side_effect = [
        _mock_secrets_response([]),
        _mock_order_get_response("ACTIVE", "https://barbican.example/v1/secrets/new-kek-uuid"),
    ]
    fake_conn.session.post.return_value = _mock_order_create_response("https://barbican.example/v1/orders/order-1")

    with (
        patch("app.services.keystone.ensure_cluster_manager_user") as mock_ensure_user,
        patch("app.services.keystone._connect_as_manager", return_value=fake_conn),
    ):

        async def _fake_ensure(_):
            return ("user-id", "password")

        mock_ensure_user.side_effect = _fake_ensure
        kek_id = asyncio.run(barbican.ensure_project_kek("proj-test"))

    assert kek_id == "new-kek-uuid"
    # POST /v1/orders 호출되었는지
    fake_conn.session.post.assert_called_once()
    post_kwargs = fake_conn.session.post.call_args.kwargs
    body = post_kwargs["json"]
    assert body["type"] == "key"
    assert body["meta"]["algorithm"] == "aes"
    assert body["meta"]["bit_length"] == 256
    assert body["meta"]["name"] == "afterglow-k8s-kek"


def test_ensure_project_kek_polls_until_active():
    """order PENDING → ACTIVE 까지 폴링."""
    import asyncio

    from app.services import barbican

    fake_conn = MagicMock()
    fake_conn.session.get_endpoint.return_value = "https://barbican.example"
    fake_conn.session.get.side_effect = [
        _mock_secrets_response([]),
        _mock_order_get_response("PENDING"),
        _mock_order_get_response("PENDING"),
        _mock_order_get_response("ACTIVE", "https://barbican.example/v1/secrets/polled-kek-uuid"),
    ]
    fake_conn.session.post.return_value = _mock_order_create_response()

    with (
        patch("app.services.keystone.ensure_cluster_manager_user") as mock_ensure_user,
        patch("app.services.keystone._connect_as_manager", return_value=fake_conn),
        patch("time.sleep"),  # 테스트 속도
    ):

        async def _fake_ensure(_):
            return ("user-id", "password")

        mock_ensure_user.side_effect = _fake_ensure
        kek_id = asyncio.run(barbican.ensure_project_kek("proj-test"))

    assert kek_id == "polled-kek-uuid"
    # GET 호출이 4번 (search 1 + poll 3)
    assert fake_conn.session.get.call_count == 4


def test_ensure_project_kek_raises_on_order_error():
    """order ERROR 응답 시 RuntimeError 전파."""
    import asyncio

    from app.services import barbican

    fake_conn = MagicMock()
    fake_conn.session.get_endpoint.return_value = "https://barbican.example"
    fake_conn.session.get.side_effect = [
        _mock_secrets_response([]),
        MagicMock(json=MagicMock(return_value={"status": "ERROR", "error_reason": "quota exceeded"})),
    ]
    fake_conn.session.post.return_value = _mock_order_create_response()

    with (
        patch("app.services.keystone.ensure_cluster_manager_user") as mock_ensure_user,
        patch("app.services.keystone._connect_as_manager", return_value=fake_conn),
    ):

        async def _fake_ensure(_):
            return ("user-id", "password")

        mock_ensure_user.side_effect = _fake_ensure
        with pytest.raises(RuntimeError, match="quota exceeded"):
            asyncio.run(barbican.ensure_project_kek("proj-test"))


# ---------------------------------------------------------------------------
# BarbicanKmsPlugin.extra_write_files — kek_id 동적 우선
# ---------------------------------------------------------------------------


def _settings_with_kms_globalkek(global_kek: str = "global-kek") -> MagicMock:
    s = MagicMock()
    s.k3s_barbican_kms_enabled = True
    s.k3s_barbican_kms_kek_id = global_kek
    s.k3s_barbican_kms_image = "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1"
    s.os_auth_url = "https://keystone.example.com:5000/v3"
    s.os_username = "admin"
    s.os_password = "secret"
    s.os_user_domain_name = "Default"
    s.os_project_name = "admin"
    s.os_project_domain_name = "Default"
    s.os_region_name = "RegionOne"
    s.os_insecure = True
    s.os_cacert = ""
    return s


def test_systemd_unit_uses_dynamic_kek_id_when_provided():
    """PR2: kek_id 인자 전달 시 systemd unit 의 --key-id 가 그 값 사용 (글로벌 fallback 무시)."""
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test", _settings_with_kms_globalkek("global-kek"), kek_id="dynamic-kek")
    unit = next(f for f in files if f["path"].endswith("barbican-kms.service"))
    assert "--key-id=dynamic-kek" in unit["content"]
    assert "--key-id=global-kek" not in unit["content"]


def test_systemd_unit_falls_back_to_global_kek_when_no_dynamic():
    """PR2 fallback: kek_id 미전달 시 settings.k3s_barbican_kms_kek_id 사용."""
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test", _settings_with_kms_globalkek("global-kek"))
    unit = next(f for f in files if f["path"].endswith("barbican-kms.service"))
    assert "--key-id=global-kek" in unit["content"]


def test_should_deploy_no_longer_requires_global_kek():
    """PR2 후: 글로벌 KEK ID 가 비어있어도 should_deploy=True (caller 가 동적 발급)."""
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    plugin = BarbicanKmsPlugin()
    s = _settings_with_kms_globalkek("")  # global KEK 비어있음
    assert plugin.should_deploy(s) is True


def test_aggregate_passes_kek_id_to_kms_plugin():
    """aggregate_extra_write_files(kek_id=...) 가 barbican_kms plugin 에 전달되어야 한다."""
    from app.services import k3s_plugins

    s = _settings_with_kms_globalkek("global-kek")
    files = k3s_plugins.aggregate_extra_write_files("proj-1", "test", s, kek_id="aggregated-kek")
    unit = next((f for f in files if f["path"].endswith("barbican-kms.service")), None)
    assert unit is not None
    assert "--key-id=aggregated-kek" in unit["content"]
