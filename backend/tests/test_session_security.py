"""B3: session ownership 이중 검증 / B4: OIDC nonce 검증 테스트"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDeleteSessionOwned:
    """소유권 이중 검증: 인덱스-데이터 user_id 불일치 시 False 반환"""

    @pytest.mark.asyncio
    async def test_mismatched_user_id_returns_false(self):
        """Redis 인덱스에는 있지만 세션 데이터의 user_id가 다르면 False를 반환한다."""
        mock_r = AsyncMock()
        mock_r.sismember.return_value = True  # 인덱스에 있음
        mock_r.get.return_value = json.dumps({"user_id": "other-user", "keystone_token": ""}).encode()

        with patch("app.services.session_store._get_redis", return_value=mock_r):
            from app.services.session_store import delete_session_owned

            result = await delete_session_owned("my-user", "some-jti", revoke_keystone=False)

        assert result is False

    @pytest.mark.asyncio
    async def test_matching_user_id_returns_true(self):
        """user_id가 일치하면 세션을 삭제하고 True를 반환한다."""
        mock_r = AsyncMock()
        mock_r.sismember.return_value = True
        mock_r.get.return_value = json.dumps({"user_id": "my-user", "keystone_token": ""}).encode()
        mock_r.delete = AsyncMock()
        mock_r.srem = AsyncMock()

        with patch("app.services.session_store._get_redis", return_value=mock_r):
            from app.services.session_store import delete_session_owned

            result = await delete_session_owned("my-user", "some-jti", revoke_keystone=False)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_in_index_returns_false(self):
        """인덱스에 없으면 raw 읽기 없이 즉시 False를 반환한다."""
        mock_r = AsyncMock()
        mock_r.sismember.return_value = False

        with patch("app.services.session_store._get_redis", return_value=mock_r):
            from app.services.session_store import delete_session_owned

            result = await delete_session_owned("my-user", "some-jti", revoke_keystone=False)

        assert result is False
        mock_r.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_stale_raw_missing_still_deletes(self):
        """인덱스에는 있지만 raw 데이터가 없으면(만료) 소유권 검증 없이 삭제를 진행한다."""
        mock_r = AsyncMock()
        mock_r.sismember.return_value = True
        mock_r.get.return_value = None  # raw 없음 (TTL 만료)
        mock_r.delete = AsyncMock()
        mock_r.srem = AsyncMock()

        with patch("app.services.session_store._get_redis", return_value=mock_r):
            from app.services.session_store import delete_session_owned

            result = await delete_session_owned("my-user", "some-jti", revoke_keystone=False)

        assert result is True


class TestOidcNonce:
    """OIDC nonce 검증 테스트"""

    @pytest.mark.asyncio
    async def test_nonce_stored_as_state_value(self):
        """get_authorize_url이 state 키에 nonce 값을 setex로 저장하는지 확인."""
        mock_r = AsyncMock()

        with patch("app.services.gitlab_oidc._get_redis", return_value=mock_r):
            import app.services.gitlab_oidc as oidc_mod

            # settings mock
            mock_settings = MagicMock()
            mock_settings.gitlab_oidc_client_id = "client-id"
            mock_settings.gitlab_oidc_redirect_uri = "https://example.com/callback"
            mock_settings.gitlab_oidc_scopes = "openid"
            mock_settings.gitlab_oidc_gitlab_url = "https://gitlab.example.com"

            with patch("app.services.gitlab_oidc.get_settings", return_value=mock_settings):
                url = await oidc_mod.get_authorize_url()

        # setex가 호출되어야 하며, 저장된 값이 "1"이 아닌 nonce 문자열이어야 한다
        assert mock_r.setex.called
        call_args = mock_r.setex.call_args
        key, ttl, value = call_args[0]
        assert key.startswith("afterglow:gitlab_state:")
        assert value != "1"
        assert len(value) > 10  # nonce는 충분히 긴 토큰이어야 함

        # URL에 nonce 파라미터가 포함되어야 한다
        assert "nonce=" in url

    @pytest.mark.asyncio
    async def test_validate_state_returns_nonce(self):
        """_validate_state가 state 검증 후 저장된 nonce 문자열을 반환한다."""
        stored_nonce = "test-nonce-value-abc123"
        mock_r = AsyncMock()
        mock_r.get.return_value = stored_nonce.encode()
        mock_r.delete = AsyncMock()

        with patch("app.services.gitlab_oidc._get_redis", return_value=mock_r):
            import app.services.gitlab_oidc as oidc_mod

            result = await oidc_mod._validate_state("some-state-token")

        assert result == stored_nonce

    @pytest.mark.asyncio
    async def test_validate_state_raises_on_missing(self):
        """유효하지 않은 state는 ValueError를 발생시킨다."""
        mock_r = AsyncMock()
        mock_r.get.return_value = None  # state 없음

        with patch("app.services.gitlab_oidc._get_redis", return_value=mock_r):
            import app.services.gitlab_oidc as oidc_mod

            # 폴백 dict도 비어있도록 보장
            oidc_mod._fallback_states.clear()

            with pytest.raises(ValueError, match="유효하지 않거나 만료된"):
                await oidc_mod._validate_state("nonexistent-state")

    @pytest.mark.asyncio
    async def test_nonce_mismatch_raises_in_exchange_code(self):
        """id_token의 nonce 클레임이 expected_nonce와 다르면 ValueError가 발생한다."""
        import base64
        import json as _json

        stored_nonce = "expected-nonce-xyz"

        # nonce가 다른 id_token payload 생성 (서명 없는 JWT 형식)
        payload = {"nonce": "wrong-nonce", "sub": "user123"}
        payload_b64 = base64.urlsafe_b64encode(_json.dumps(payload).encode()).decode().rstrip("=")
        fake_id_token = f"header.{payload_b64}.signature"

        mock_r = AsyncMock()
        # _validate_state가 stored_nonce를 반환
        mock_r.get.return_value = stored_nonce.encode()
        mock_r.delete = AsyncMock()

        import app.services.gitlab_oidc as oidc_mod

        with patch("app.services.gitlab_oidc._get_redis", return_value=mock_r):
            with patch.object(
                oidc_mod,
                "_exchange_gitlab_code",
                return_value={
                    "access_token": "at",
                    "id_token": fake_id_token,
                },
            ):
                with pytest.raises(ValueError, match="nonce 불일치"):
                    await oidc_mod.exchange_code("auth-code", "some-state")

    @pytest.mark.asyncio
    async def test_nonce_match_proceeds(self):
        """id_token의 nonce가 일치하면 federated auth로 진행한다."""
        import base64
        import json as _json

        stored_nonce = "correct-nonce-abc"

        payload = {"nonce": stored_nonce, "sub": "user123"}
        payload_b64 = base64.urlsafe_b64encode(_json.dumps(payload).encode()).decode().rstrip("=")
        fake_id_token = f"header.{payload_b64}.signature"

        mock_r = AsyncMock()
        mock_r.get.return_value = stored_nonce.encode()
        mock_r.delete = AsyncMock()

        import app.services.gitlab_oidc as oidc_mod

        fed_result = {
            "token": "unscoped-token",
            "user": {"id": "user-id-1"},
        }
        scoped_result = {
            "token": "scoped-token",
            "project_id": "proj-1",
            "project_name": "My Project",
            "user_id": "user-id-1",
            "username": "testuser",
            "expires_at": "2099-01-01T00:00:00Z",
            "roles": ["member"],
        }

        with patch("app.services.gitlab_oidc._get_redis", return_value=mock_r):
            with patch.object(
                oidc_mod,
                "_exchange_gitlab_code",
                return_value={
                    "access_token": "at",
                    "id_token": fake_id_token,
                },
            ):
                with patch.object(oidc_mod, "_federated_auth", return_value=fed_result):
                    with patch.object(oidc_mod, "_list_projects_for_token", return_value=[{"id": "proj-1"}]):
                        with patch.object(oidc_mod, "_get_user_default_project_id", return_value="proj-1"):
                            with patch.object(oidc_mod, "_scope_token", return_value=scoped_result):
                                result = await oidc_mod.exchange_code("auth-code", "some-state")

        assert result["project_id"] == "proj-1"
        assert result["default_project_id"] == "proj-1"
        assert result["token"] == "scoped-token"

    @pytest.mark.asyncio
    async def test_exchange_code_omits_inaccessible_default_project_id(self):
        """접근 불가능한 default project는 응답에서 제거하고 첫 접근 가능 프로젝트로 scope한다."""
        import base64
        import json as _json

        stored_nonce = "correct-nonce-abc"

        payload = {"nonce": stored_nonce, "sub": "user123"}
        payload_b64 = base64.urlsafe_b64encode(_json.dumps(payload).encode()).decode().rstrip("=")
        fake_id_token = f"header.{payload_b64}.signature"

        mock_r = AsyncMock()
        mock_r.get.return_value = stored_nonce.encode()
        mock_r.delete = AsyncMock()

        import app.services.gitlab_oidc as oidc_mod

        fed_result = {
            "token": "unscoped-token",
            "user": {"id": "user-id-1"},
        }
        scoped_result = {
            "token": "scoped-token",
            "project_id": "proj-1",
            "project_name": "My Project",
            "user_id": "user-id-1",
            "username": "testuser",
            "expires_at": "2099-01-01T00:00:00Z",
            "roles": ["member"],
        }
        scope_token = AsyncMock(return_value=scoped_result)

        with patch("app.services.gitlab_oidc._get_redis", return_value=mock_r):
            with patch.object(
                oidc_mod,
                "_exchange_gitlab_code",
                return_value={
                    "access_token": "at",
                    "id_token": fake_id_token,
                },
            ):
                with patch.object(oidc_mod, "_federated_auth", return_value=fed_result):
                    with patch.object(
                        oidc_mod,
                        "_list_projects_for_token",
                        return_value=[{"id": "proj-1"}, {"id": "proj-2"}],
                    ):
                        with patch.object(oidc_mod, "_get_user_default_project_id", return_value="missing-proj"):
                            with patch.object(oidc_mod, "_scope_token", scope_token):
                                result = await oidc_mod.exchange_code("auth-code", "some-state")

        scope_token.assert_awaited_once_with("unscoped-token", "proj-1")
        assert result["default_project_id"] == ""


class TestSessionConcurrency:
    """동시 세션 토큰/활동/블랙리스트 갱신 시 보안 필드 유실 방지 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_session_updates_preserve_security_fields(self):
        """controlled Redis schedule로 동시 update_session_token, touch_session_seen, blacklist_session 실행 시
        새 Keystone 토큰, 블랙리스트 상태, last_seen 필드가 모두 보존되어야 한다."""
        import asyncio
        import time

        from app.services.session_store import (
            _get_redis,
            blacklist_session,
            get_session,
            store_session,
            touch_session_seen,
            update_session_token,
        )

        jti = "jti-concurrent-test"
        exp = int(time.time()) + 3600
        await store_session(jti, "ks-token-original", "proj-1", "user-1", exp)

        r = await _get_redis()
        original_get = r.get

        read_barrier = asyncio.Event()
        read_count = 0

        async def controlled_get(name, *args, **kwargs):
            res = await original_get(name, *args, **kwargs)
            name_str = name.decode() if isinstance(name, bytes) else str(name)
            if jti in name_str:
                nonlocal read_count
                read_count += 1
                if read_count == 3:
                    read_barrier.set()
                else:
                    await read_barrier.wait()
            return res

        with patch.object(r, "get", side_effect=controlled_get):
            await asyncio.gather(
                update_session_token(jti, "ks-token-NEW-ROTATED"),
                touch_session_seen(jti, "192.168.1.100", "fp-12345"),
                blacklist_session(jti, "security violation"),
            )

        sess = await get_session(jti)
        assert sess is not None
        # 새로 회전된 Keystone 토큰이 stale read writeback에 의해 덮어씌워지지 않고 보존되어야 함
        assert sess.get("keystone_token") == "ks-token-NEW-ROTATED"
        # 블랙리스트 상태가 보존되어야 함
        assert sess.get("blacklisted") is True
        # last_ip activity 정보가 보존되어야 함
        assert sess.get("last_ip") == "192.168.1.100"
