from _pytest._io.saferepr import saferepr

from tests.integration.conftest import (
    IntegrationAuthSession,
    RedactedCredentials,
    RedactedMapping,
    RedactedSecret,
)


def test_integration_auth_session_repr_never_exposes_credentials_or_tokens():
    session = IntegrationAuthSession(
        credentials={"username": "test-user", "password": "secret-password"},
        label="integration user",
        token_data={"token": "access-token", "refresh_token": "refresh-token"},
    )

    rendered = repr(session)

    assert rendered == "IntegrationAuthSession(label='integration user', authenticated=True)"
    assert "secret-password" not in rendered
    assert "access-token" not in rendered
    assert "refresh-token" not in rendered


def test_integration_credentials_repr_never_exposes_mapping_values():
    credentials = RedactedCredentials({"username": "test-user", "password": "secret-password"})
    bad_credentials = RedactedCredentials({**credentials, "password": "wrong-password"})

    for rendered in (repr(credentials), repr(bad_credentials)):
        assert rendered.startswith("RedactedCredentials(keys=")
        assert "test-user" not in rendered
        assert "secret-password" not in rendered
        assert "wrong-password" not in rendered


def test_pytest_safe_repr_redacts_auth_response_and_token_values():
    auth_data = RedactedMapping({"token": "access-token", "refresh_token": "refresh-token"})
    token = RedactedSecret("access-token")

    for rendered in (saferepr(auth_data), saferepr(token)):
        assert "access-token" not in rendered
        assert "refresh-token" not in rendered
