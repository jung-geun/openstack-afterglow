"""Grafana JWT 발급 엔드포인트 단위 테스트."""

import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest


def _decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


@pytest.mark.asyncio
async def test_issue_grafana_token_returns_jwt(client):
    """유효한 설정 시 JWT + grafana_url + expires_in 반환."""
    fake_settings = MagicMock()
    fake_settings.grafana_jwt_secret = "super-secret"
    fake_settings.grafana_base_url = "https://grafana.example.com"

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.post("/api/grafana/token")

    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["grafana_url"] == "https://grafana.example.com"
    assert data["expires_in"] == 3600
    assert len(data["token"].split(".")) == 3


@pytest.mark.asyncio
async def test_grafana_token_contains_correct_claims(client):
    """발급된 JWT에 user_id, username, project_id, role 클레임이 포함된다."""
    fake_settings = MagicMock()
    fake_settings.grafana_jwt_secret = "my-secret"
    fake_settings.grafana_base_url = ""

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.post("/api/grafana/token")

    assert resp.status_code == 200
    token = resp.json()["token"]
    payload = _decode_jwt_payload(token)

    assert payload["sub"] == "test-user-123"
    assert payload["login"] == "testuser"
    assert payload["project_id"] == "test-project-123"
    assert payload["role"] == "Viewer"
    assert payload["exp"] > int(time.time())


@pytest.mark.asyncio
async def test_grafana_token_missing_secret_returns_503(client):
    """grafana_jwt_secret 미설정 시 503 반환."""
    fake_settings = MagicMock()
    fake_settings.grafana_jwt_secret = ""

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.post("/api/grafana/token")

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_grafana_token_admin_role(admin_client):
    """admin 사용자는 JWT role이 Editor로 발급된다."""
    fake_settings = MagicMock()
    fake_settings.grafana_jwt_secret = "my-secret"
    fake_settings.grafana_base_url = ""

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await admin_client.post("/api/grafana/token")

    assert resp.status_code == 200
    token = resp.json()["token"]
    payload = _decode_jwt_payload(token)
    assert payload["role"] == "Editor"
