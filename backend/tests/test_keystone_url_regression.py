"""Keystone URL 정규화 — 직접 결합 경로 회귀 테스트.

os_auth_url에 /v3 suffix 없이 입력해도 revoke_token / _federated_auth 가 올바른
/v3/... path를 호출하는지 검증.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_settings(auth_url: str) -> MagicMock:
    s = MagicMock()
    s.os_auth_url = auth_url
    s.ssl_verify = True
    s.gitlab_oidc_idp_id = "gitlab"
    s.gitlab_oidc_protocol_id = "openid"
    return s


def test_revoke_token_uses_normalized_url() -> None:
    """revoke_token: os_auth_url에 /v3 없어도 DELETE URL이 /v3/auth/tokens."""
    # Pydantic validator가 정규화하므로 settings에는 이미 /v3가 붙은 값이 들어있다.
    # 이 테스트는 실제 Settings 객체를 사용해 validator → 결합 경로까지 end-to-end 검증.
    from app.config import Settings

    s = Settings(os_auth_url="https://keystone.test")
    assert s.os_auth_url == "https://keystone.test/v3"

    # revoke_token이 sess.delete에 넘기는 URL 검증
    fake_sess = MagicMock()
    with (
        patch("app.services.keystone.get_settings", return_value=s),
        patch("app.services.keystone.ks_session.Session", return_value=fake_sess),
        patch("app.services.keystone.v3.Token"),
    ):
        from app.services.keystone import revoke_token

        revoke_token("tok-abc")

    called_url = fake_sess.delete.call_args[0][0]
    assert called_url == "https://keystone.test/v3/auth/tokens", f"expected /v3/auth/tokens, got: {called_url}"


@pytest.mark.asyncio
async def test_federated_auth_uses_normalized_url() -> None:
    """_federated_auth: os_auth_url /v3 없어도 POST URL이 /v3/OS-FEDERATION/..."""
    from app.config import Settings

    s = Settings(os_auth_url="https://keystone.test")
    assert s.os_auth_url == "https://keystone.test/v3"

    mock_resp = MagicMock()
    mock_resp.headers = {"X-Subject-Token": "unscoped-tok"}
    mock_resp.json.return_value = {"token": {"user": {"id": "u-1", "name": "alice"}}}
    mock_resp.raise_for_status = MagicMock()

    captured_url = []

    async def fake_post(url, **kwargs):
        captured_url.append(url)
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = fake_post

    with (
        patch("app.services.gitlab_oidc.get_settings", return_value=s),
        patch("app.services.gitlab_oidc.httpx.AsyncClient", return_value=mock_client),
    ):
        from app.services.gitlab_oidc import _federated_auth

        await _federated_auth("id-token-xyz")

    assert captured_url, "POST가 한 번도 호출되지 않음"
    url = captured_url[0]
    assert "/v3/OS-FEDERATION/" in url, f"expected /v3/OS-FEDERATION/ in URL, got: {url}"
