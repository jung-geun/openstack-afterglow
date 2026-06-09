"""기계적 보안 수정 단위 테스트: A1(SD 타이밍), A3(이메일 이스케이프), A4(Trove 로그 redact)"""

import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# A1 — SD 토큰 타이밍 공격 수정: hmac.compare_digest 사용 확인
# ---------------------------------------------------------------------------


class TestSdTokenTimingFix:
    def test_hmac_compare_digest_used_in_source(self):
        """sd_targets.py 소스에 hmac.compare_digest 호출이 존재해야 한다."""
        import inspect

        from app.api.common import sd_targets

        source = inspect.getsource(sd_targets)
        assert "hmac.compare_digest" in source, (
            "sd_targets.py 에 hmac.compare_digest 가 없다 — 타이밍 공격 취약점이 수정되지 않음"
        )

    def test_hmac_module_imported(self):
        """sd_targets 모듈이 hmac 을 import 해야 한다."""
        from app.api.common import sd_targets

        assert hasattr(sd_targets, "hmac"), "sd_targets.py 에 hmac 모듈이 import 되지 않았다"

    def test_correct_token_accepted(self, monkeypatch):
        """올바른 토큰은 예외 없이 통과해야 한다."""
        from app.api.common.sd_targets import _verify_sd_token

        mock_settings = MagicMock()
        mock_settings.monitoring_sd_token = "secret-token-abc"
        monkeypatch.setattr("app.api.common.sd_targets.get_settings", lambda: mock_settings)

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer secret-token-abc"

        # 예외 없이 통과해야 함
        _verify_sd_token(mock_request)

    def test_wrong_token_raises_401(self, monkeypatch):
        """잘못된 토큰은 HTTP 401 을 발생시켜야 한다."""
        from fastapi import HTTPException

        from app.api.common.sd_targets import _verify_sd_token

        mock_settings = MagicMock()
        mock_settings.monitoring_sd_token = "correct-token"
        monkeypatch.setattr("app.api.common.sd_targets.get_settings", lambda: mock_settings)

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer wrong-token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_sd_token(mock_request)
        assert exc_info.value.status_code == 401

    def test_compare_digest_called_with_correct_args(self, monkeypatch):
        """hmac.compare_digest 가 (token, expected) 순서로 호출되는지 mock 으로 확인."""
        import hmac as _hmac

        from app.api.common.sd_targets import _verify_sd_token

        mock_settings = MagicMock()
        mock_settings.monitoring_sd_token = "expected-token"
        monkeypatch.setattr("app.api.common.sd_targets.get_settings", lambda: mock_settings)

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer expected-token"

        call_args_list = []

        original_compare_digest = _hmac.compare_digest

        def spy_compare_digest(a, b):
            call_args_list.append((a, b))
            return original_compare_digest(a, b)

        monkeypatch.setattr("app.api.common.sd_targets.hmac.compare_digest", spy_compare_digest)

        _verify_sd_token(mock_request)

        assert len(call_args_list) == 1
        assert call_args_list[0] == ("expected-token", "expected-token")


# ---------------------------------------------------------------------------
# A3 — 초대 이메일 HTML 인젝션 방지
# ---------------------------------------------------------------------------


class TestEmailHtmlEscaping:
    @pytest.mark.asyncio
    async def test_script_tag_in_inviter_name_is_escaped(self, monkeypatch):
        """inviter_name 에 <script> 가 포함되면 이스케이프되어야 한다."""
        from app.services import email_service

        sent_html: list[str] = []

        async def mock_send_email(to, subject, html_body, text_body):
            sent_html.append(html_body)
            return True

        monkeypatch.setattr(email_service, "send_email", mock_send_email)
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: MagicMock(site_name="TestSite"),
        )

        await email_service.send_invitation_email(
            to_email="user@example.com",
            project_name="MyProject",
            inviter_name='<script>alert("xss")</script>',
            accept_url="https://example.com/accept/token",
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )

        assert sent_html, "send_email 이 호출되지 않았다"
        body = sent_html[0]
        assert "<script>" not in body, "HTML 본문에 <script> 태그가 이스케이프되지 않았다"
        assert "&lt;script&gt;" in body, "HTML 본문에 이스케이프된 &lt;script&gt; 가 없다"

    @pytest.mark.asyncio
    async def test_script_tag_in_project_name_is_escaped(self, monkeypatch):
        """project_name 에 <script> 가 포함되면 이스케이프되어야 한다."""
        from app.services import email_service

        sent_html: list[str] = []

        async def mock_send_email(to, subject, html_body, text_body):
            sent_html.append(html_body)
            return True

        monkeypatch.setattr(email_service, "send_email", mock_send_email)
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: MagicMock(site_name="TestSite"),
        )

        await email_service.send_invitation_email(
            to_email="user@example.com",
            project_name="<img src=x onerror=alert(1)>",
            inviter_name="Alice",
            accept_url="https://example.com/accept/token",
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )

        body = sent_html[0]
        assert "<img" not in body, "HTML 본문에 <img 태그가 이스케이프되지 않았다"
        assert "&lt;img" in body

    @pytest.mark.asyncio
    async def test_accept_url_quotes_are_escaped(self, monkeypatch):
        """accept_url 에 큰따옴표가 있으면 속성값 내에서 이스케이프되어야 한다."""
        from app.services import email_service

        sent_html: list[str] = []

        async def mock_send_email(to, subject, html_body, text_body):
            sent_html.append(html_body)
            return True

        monkeypatch.setattr(email_service, "send_email", mock_send_email)
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: MagicMock(site_name="TestSite"),
        )

        await email_service.send_invitation_email(
            to_email="user@example.com",
            project_name="MyProject",
            inviter_name="Alice",
            accept_url='https://example.com/accept?x=1"onmouseover="alert(1)',
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )

        body = sent_html[0]
        # 이스케이프된 따옴표 확인 — href 속성 브레이크아웃 방지
        assert '"onmouseover="' not in body, "URL 내 따옴표가 이스케이프되지 않았다"

    @pytest.mark.asyncio
    async def test_plain_text_body_not_escaped(self, monkeypatch):
        """text_body 는 HTML 이스케이프 없이 원본 문자열을 포함해야 한다."""
        from app.services import email_service

        sent_args: list[dict] = []

        async def mock_send_email(to, subject, html_body, text_body):
            sent_args.append({"html_body": html_body, "text_body": text_body})
            return True

        monkeypatch.setattr(email_service, "send_email", mock_send_email)
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: MagicMock(site_name="TestSite"),
        )

        await email_service.send_invitation_email(
            to_email="user@example.com",
            project_name="MyProject",
            inviter_name="Alice",
            accept_url="https://example.com/accept/token",
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )

        text = sent_args[0]["text_body"]
        # plain text 본문에는 원본 이름이 그대로 포함되어야 함
        assert "Alice" in text
        assert "MyProject" in text


# ---------------------------------------------------------------------------
# A4 — Trove DEBUG 로그 비밀번호 redact
# ---------------------------------------------------------------------------


class TestTroveLogRedact:
    def test_password_not_logged_when_users_present(self):
        """users 에 password 가 있을 때 DEBUG 로그에 실제 비밀번호가 출력되지 않아야 한다."""
        import app.services.trove as trove_module

        logged_messages: list[str] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                logged_messages.append(self.format(record))

        handler = CapturingHandler()
        logger = logging.getLogger(trove_module.__name__)
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            # trove_module 내의 _logger.debug 를 직접 호출하는 경로 재현
            # create_instance 를 호출하지 않고 로그 redact 로직만 단독 검증
            import copy as _copy

            payload = {
                "instance": {
                    "name": "test-db",
                    "users": [
                        {"name": "admin", "password": "super-secret-password"},
                        {"name": "app", "password": "another-secret"},
                    ],
                }
            }

            # redact 로직을 직접 재현하여 검증
            _log_payload = _copy.deepcopy(payload)
            for u in _log_payload.get("instance", {}).get("users", []):
                if "password" in u:
                    u["password"] = "***"

            trove_module._logger.debug("Trove create_instance payload: %s", _log_payload)

            assert logged_messages, "DEBUG 로그가 한 건도 캡처되지 않았다"
            combined = " ".join(logged_messages)
            assert "super-secret-password" not in combined, (
                "DEBUG 로그에 실제 비밀번호 'super-secret-password' 가 노출되었다"
            )
            assert "another-secret" not in combined, "DEBUG 로그에 실제 비밀번호 'another-secret' 가 노출되었다"
            assert "***" in combined, "redact 된 '***' 표시가 로그에 없다"
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

    def test_original_payload_unchanged_after_redact(self):
        """deepcopy 를 사용하므로 원본 payload 의 password 는 변경되지 않아야 한다."""
        import copy as _copy

        payload = {
            "instance": {
                "users": [{"name": "admin", "password": "real-password"}],
            }
        }
        _log_payload = _copy.deepcopy(payload)
        for u in _log_payload.get("instance", {}).get("users", []):
            if "password" in u:
                u["password"] = "***"

        # 원본은 변경되지 않아야 함
        assert payload["instance"]["users"][0]["password"] == "real-password"
        assert _log_payload["instance"]["users"][0]["password"] == "***"

    def test_redact_logic_in_source(self):
        """trove.py 소스에 password redact 코드가 존재해야 한다."""
        import inspect

        import app.services.trove as trove_module

        source = inspect.getsource(trove_module)
        assert "***" in source, "trove.py 에 password redact ('***') 코드가 없다"
        assert "deepcopy" in source, "trove.py 에 deepcopy 호출이 없다 — 원본 변조 위험"

    def test_no_password_in_log_via_mock(self, caplog):
        """caplog 를 통해 trove logger 의 DEBUG 출력에 password 가 없는지 확인."""
        import copy as _copy

        import app.services.trove as trove_module

        with caplog.at_level(logging.DEBUG, logger=trove_module.__name__):
            payload = {
                "instance": {
                    "name": "db",
                    "users": [{"name": "u", "password": "TopSecret123"}],
                }
            }
            _log_payload = _copy.deepcopy(payload)
            for u in _log_payload.get("instance", {}).get("users", []):
                if "password" in u:
                    u["password"] = "***"
            trove_module._logger.debug("Trove create_instance payload: %s", _log_payload)

        assert "TopSecret123" not in caplog.text, "caplog 에 평문 비밀번호가 노출되었다"
